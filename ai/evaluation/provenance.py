"""Dataset provenance + claim policy for every evaluation report.

Three tracks, never silently mixed:
  synthetic     -- only synthetic rows; may never be described as real-world accuracy
  real_holdout  -- only real public rows from a held-out split; the ONLY track that can support a
                   (scoped) real-data claim, and only when its conditions hold
  hybrid        -- both kinds, always reported as separate slices; no pooled headline number
"""
from __future__ import annotations

from collections import Counter, defaultdict

TRACKS = ("synthetic", "real_holdout", "hybrid")
DESCRIPTIVE = "descriptive"   # statistics about real data (e.g. taxonomy coverage); makes no model-performance claim
MIN_REAL_N = 200            # below this a real-data claim is not allowed (wide intervals)


class TrackError(ValueError):
    """The rows supplied do not belong on the requested evaluation track."""


def row_provenance(row: dict) -> dict:
    """Provenance of one eval row. Understands canonical records/pairs and the legacy synthetic eval files."""
    p = row.get("provenance")
    if p:
        return p
    if row.get("synthetic") is True:
        return {"kind": "synthetic", "source_id": "synthetic_civic", "source_dataset": "CivicConnect synthetic reports",
                "license_id": "project-owned", "license_verified": True, "label_origin": "synthetic_template",
                "source_version": row.get("generator_version")}
    raise TrackError("row has no provenance and is not marked synthetic: refusing to evaluate unlabeled data")


def build_provenance(rows: list[dict]) -> dict:
    kinds: Counter = Counter()
    per: dict[str, dict] = defaultdict(lambda: {"n": 0, "label_origins": Counter(), "text_origins": Counter()})
    for r in rows:
        p = row_provenance(r)
        kinds[p["kind"]] += 1
        s = per[p["source_id"]]
        s["n"] += 1
        s.update(kind=p["kind"], dataset=p.get("source_dataset"), version=p.get("source_version"), license_id=p.get("license_id"),
                 license_verified=bool(p.get("license_verified")), origin_verified=bool(p.get("origin_verified", True)),
                 mapping_id=p.get("mapping_id"), mapping_version=p.get("mapping_version"))
        s["label_origins"][p.get("label_origin")] += 1
        s["text_origins"][r.get("text_origin", "n/a")] += 1
    return {"n": len(rows), "kinds": dict(kinds),
            "sources": {k: {**{x: y for x, y in v.items() if x not in ("label_origins", "text_origins")},
                            "label_origins": dict(v["label_origins"]), "text_origins": dict(v["text_origins"])} for k, v in per.items()}}


def validate_track(track: str, prov: dict, *, task: str | None = None, rows: list[dict] | None = None) -> None:
    kinds = set(prov["kinds"])
    if track == DESCRIPTIVE:
        if kinds != {"real_public"}:
            raise TrackError(f"descriptive statistics apply to real_public rows, got {sorted(kinds)}")
        return
    if track not in TRACKS:
        raise TrackError(f"unknown track {track!r}")
    if track == "synthetic" and kinds != {"synthetic"}:
        raise TrackError(f"synthetic track received {sorted(kinds)} rows; use real_holdout or hybrid for real data")
    if track == "real_holdout":
        if kinds != {"real_public"}:
            raise TrackError(f"real_holdout track requires only real_public rows, got {sorted(kinds)}")
        if rows is not None and any(r.get("split_hint") not in ("holdout", "test") for r in rows):
            raise TrackError("real_holdout evaluates only rows with split_hint holdout/test; prepare the data with a holdout "
                             "(--holdout-after / --holdout-countries) so training rows can never be scored")
        if task == "intake" and rows is not None and any(r.get("text_origin") != "citizen_narrative" for r in rows):
            raise TrackError("intake evaluation needs genuine citizen narrative text. These rows have none (or only source-category text, "
                             "which would be label leakage), so text-classifier accuracy cannot be evaluated on this real data")
    if track == "hybrid" and kinds != {"synthetic", "real_public"}:
        raise TrackError(f"hybrid track needs both synthetic and real_public rows, got {sorted(kinds)}")


def claims_for(track: str, prov: dict) -> dict:
    """What the reader may and may not conclude from the numbers of this report."""
    real_n = sum(v["n"] for v in prov["sources"].values() if v.get("kind") == "real_public")
    unverified = sorted(k for k, v in prov["sources"].items() if v.get("kind") == "real_public" and not v.get("license_verified"))
    unknown_origin = sorted(k for k, v in prov["sources"].items() if v.get("kind") == "real_public" and not v.get("origin_verified", True))
    if track == DESCRIPTIVE:
        return {"track": track, "real_world_accuracy_claim_allowed": False, "pooled_headline_allowed": True,
                "banner": "DESCRIPTIVE statistics of real public data under a DRAFT taxonomy mapping — not model performance."
                          + (" ORIGIN UNVERIFIED (may not be real records): " + ", ".join(unknown_origin) if unknown_origin else ""),
                "reasons": ["no model is evaluated"] + ([f"licence not verified for {unverified}"] if unverified else [])
                + ([f"origin not verified (real vs simulated/derived) for {unknown_origin}"] if unknown_origin else [])}
    if track == "synthetic":
        return {"track": track, "real_world_accuracy_claim_allowed": False, "pooled_headline_allowed": True,
                "banner": "SYNTHETIC DATA ONLY — not an estimate of real-world accuracy.", "reasons": ["all rows are synthetic"]}
    if track == "hybrid":
        reasons = ["hybrid report: synthetic and real slices are reported separately; no pooled number is a real-world estimate"]
        if unknown_origin:
            reasons.append(f"origin not verified for {unknown_origin}: the 'real' slice may not be real")
        return {"track": track, "real_world_accuracy_claim_allowed": False, "pooled_headline_allowed": False,
                "banner": "HYBRID (synthetic + real) — read the slices separately; synthetic slice is NOT real-world accuracy.",
                "reasons": reasons, "real_slice_claim": {**_real_claim(real_n, unverified, prov), **({"allowed": False} if unknown_origin else {})}}
    c = _real_claim(real_n, unverified, prov)
    if unknown_origin:
        c["allowed"] = False
        c["reasons"].append(f"origin not verified (real vs simulated/derived) for {unknown_origin}: cannot be called real-world evidence")
    return {"track": track, "real_world_accuracy_claim_allowed": c["allowed"], "pooled_headline_allowed": True,
            "banner": ("REAL PUBLIC DATA HOLDOUT — " + c["scope"]) if c["allowed"] else
                      "REAL PUBLIC DATA HOLDOUT — claim NOT allowed: " + "; ".join(c["reasons"]),
            "reasons": c["reasons"], "scope": c["scope"]}


def _real_claim(real_n: int, unverified: list[str], prov: dict) -> dict:
    reasons = []
    if real_n < MIN_REAL_N:
        reasons.append(f"only {real_n} real rows (< {MIN_REAL_N})")
    if unverified:
        reasons.append(f"licence not verified for {unverified}: results must not be published")
    srcs = [k for k, v in prov["sources"].items() if v.get("kind") == "real_public"]
    origins = sorted({o for k in srcs for o in prov["sources"][k]["label_origins"]})
    scope = (f"agreement with {'/'.join(origins) or 'source'} labels of {', '.join(srcs)} (mapped to taxonomy via an explicit draft mapping) "
             f"on a held-out split; city/country-specific; not ground truth for other regions")
    return {"allowed": not reasons, "reasons": reasons, "scope": scope}
