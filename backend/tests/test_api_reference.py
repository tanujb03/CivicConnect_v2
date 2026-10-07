"""Reference data (taxonomy, departments, wards): any authenticated user, ETag + Cache-Control, 304 on a matching If-None-Match."""
import pytest

from backend.services.taxonomy import taxonomy

ROLE_KEYS = ["alice", "roads_worker", "roads_op", "roads_mgr", "ward_officer", "admin", "overlooker"]          # one user of every role in the `staffed` cast
PATHS = ["/api/v1/reference/taxonomy", "/api/v1/reference/departments", "/api/v1/reference/wards"]


@pytest.mark.parametrize("path", PATHS)
def test_every_authenticated_role_can_read_and_anonymous_cannot(staffed, path):
    e = staffed
    assert e.client.get(path).status_code == 401
    for who in ROLE_KEYS:
        r = e.client.get(path, headers=e.headers(who))
        assert r.status_code == 200, (who, r.text)
        assert r.headers["etag"].startswith('"') and r.headers["cache-control"].startswith("private, max-age=")


def test_taxonomy_is_exactly_the_ai_taxonomy(staffed):
    e, raw = staffed, taxonomy().raw
    body = e.client.get("/api/v1/reference/taxonomy", headers=e.headers("alice")).json()
    assert body["categories"] == raw["categories"]                        # categories and subcategories exactly as in the AI taxonomy
    assert [d["id"] for d in body["departments"]] == [d["id"] for d in raw["departments"]]
    assert body["version"] == raw["taxonomy_version"] and body["supported_languages"] == raw["supported_languages"]
    assert {p["id"] for p in body["priorities"]} == {"LOW", "NORMAL", "HIGH", "URGENT"} and {s["id"] for s in body["severities"]} == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert len(body["categories"]) == 9 and sum(len(c["subcategories"]) for c in body["categories"]) == 27
    assert not {"review", "id_conventions", "aliases"} & set(body)         # internal notes are not published


@pytest.mark.parametrize("path", PATHS)
def test_etag_revalidation_returns_304_with_an_empty_body(staffed, path):
    e = staffed
    first = e.client.get(path, headers=e.headers("alice"))
    etag = first.headers["etag"]
    again = e.client.get(path, headers={**e.headers("alice"), "If-None-Match": etag})
    assert again.status_code == 304 and again.content == b"" and again.headers["etag"] == etag and "max-age" in again.headers["cache-control"]
    assert e.client.get(path, headers={**e.headers("alice"), "If-None-Match": f'"other", W/{etag}'}).status_code == 304     # a list and weak validators match too
    assert e.client.get(path, headers={**e.headers("alice"), "If-None-Match": '"stale"'}).status_code == 200
    assert e.client.get(path, headers={"If-None-Match": etag}).status_code == 401                                         # the ETag never bypasses authentication


def test_the_etag_changes_when_the_data_changes(staffed):
    from backend.models import Department
    e = staffed
    before = e.client.get("/api/v1/reference/departments", headers=e.headers("alice")).headers["etag"]
    with e.session_factory() as db:
        db.get(Department, "road_maintenance").name = "Roads (renamed)"
        db.commit()
    r = e.client.get("/api/v1/reference/departments", headers={**e.headers("alice"), "If-None-Match": before})
    assert r.status_code == 200 and r.headers["etag"] != before and any(d["name"] == "Roads (renamed)" for d in r.json()["items"])


def test_departments_cover_the_taxonomy_departments(staffed):
    e = staffed
    items = e.client.get("/api/v1/reference/departments", headers=e.headers("alice")).json()["items"]
    assert {d["id"] for d in items} == set(taxonomy().departments)
    assert {"id", "code", "name", "description", "name_i18n", "category_coverage"} <= set(items[0])


def test_wards_have_centroid_and_bbox_and_boundary_only_on_request(staffed):
    e = staffed
    plain = e.client.get("/api/v1/reference/wards", headers=e.headers("alice")).json()["items"]
    assert len(plain) == 10 and all("boundary" not in w for w in plain)
    w = plain[0]
    assert {"id", "label", "name", "centroid", "bbox"} <= set(w)
    min_lon, min_lat, max_lon, max_lat = w["bbox"]
    assert min_lon <= w["centroid"]["longitude"] <= max_lon and min_lat <= w["centroid"]["latitude"] <= max_lat
    full = e.client.get("/api/v1/reference/wards?include=boundary", headers=e.headers("alice"))
    assert full.status_code == 200 and all(x["boundary"]["type"] == "Polygon" for x in full.json()["items"])
    assert full.headers["etag"] != e.client.get("/api/v1/reference/wards", headers=e.headers("alice")).headers["etag"]
    assert e.client.get("/api/v1/reference/wards?include=everything", headers=e.headers("alice")).status_code == 422


def test_bbox_handles_missing_and_multi_polygon_boundaries():
    from backend.services.reference import bbox
    assert bbox(None) is None and bbox({}) is None and bbox({"type": "Polygon", "coordinates": []}) is None
    assert bbox({"type": "MultiPolygon", "coordinates": [[[[1, 2], [3, 2], [3, 5], [1, 2]]], [[[10, -1], [11, -1], [11, 0], [10, -1]]]]}) == [1, -1, 11, 5]
