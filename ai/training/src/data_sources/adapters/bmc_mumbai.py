"""Mumbai Nagar Seva BMC civic complaints (Kaggle competition data) -> CaseRecord, under a column-role policy.

The competition data is SYNTHETICALLY GENERATED (see the card): records carry kind ``synthetic_third_party`` and can never
support a real-world claim. Not an official BMC source. Column names are NOT known: roles are resolved by alias and/or an
explicit operator ``role_map`` read from the dataset's data dictionary; ambiguity fails loudly; every unclaimed
column is *unclassified* and never read. PII and sensitive-attribute roles are never read or stored, post-resolution
free text is never stored, and the free-text ``description`` is only stored when the operator has confirmed it is
citizen-written. ``CaseRecord.department`` is deliberately left empty: filling it from the taxonomy would make
category->department circular as a routing target.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterator

from ..canonical import CaseRecord, Provenance
from ..card_schema import SourceCard
from ..column_roles import NEVER_PHASES, RoleResolution, TaskPolicy, coerce
from ..columns import iter_rows, parse_coord, parse_ts, reservoir, sniff_headers
from ..errors import SchemaMismatch
from ..mapping import CoverageReport, DepartmentMapping, MappingTable

REQUIRED_ROLES = ("source_category", "created_at")
MUMBAI_BBOX = (18.85, 72.75, 19.35, 73.05)   # lat_min, lon_min, lat_max, lon_max: sanity statistic only, never a filter
MAX_UNPARSED_DATE_SHARE = 0.2


class BMCMumbaiAdapter:
    source_id = "bmc_mumbai"

    def __init__(self, card: SourceCard, mapping: MappingTable, dept_mapping: DepartmentMapping, policy: TaskPolicy, *,
                 retrieved_at: str | None = None, role_map: dict[str, str] | None = None, confirm_citizen_text: bool = False,
                 row_index_ids: bool = False, resolution_unit: str | None = None):
        if resolution_unit not in (None, "hours", "days"):
            raise SchemaMismatch("resolution_unit must be 'hours' or 'days'")
        if confirm_citizen_text and card.is_synthetic:
            raise SchemaMismatch(f"{card.id} is synthetic: its description column cannot be confirmed as citizen-written, so --confirm-citizen-text is refused. "
                                 "Free text from a synthetic source is never used as citizen narrative.")
        self.card, self.mapping, self.dept_mapping, self.policy = card, mapping, dept_mapping, policy
        self.retrieved_at, self.role_map = retrieved_at, role_map or {}
        self.confirm_citizen_text, self.row_index_ids, self.resolution_unit = confirm_citizen_text, row_index_ids, resolution_unit
        self.coverage = CoverageReport()
        self.resolution: RoleResolution | None = None
        self.stats = {"rows_read": 0, "dropped_no_id": 0, "duplicate_ids": 0, "no_created_at": 0, "no_coordinates": 0, "outside_mumbai_bbox": 0,
                      "negative_duration": 0, "unresolved_no_closed_at": 0, "duration_unit_unknown": 0}

    def provenance(self, rid: str | None) -> Provenance:
        c = self.card
        return Provenance(kind=c.kind, source_id=c.id, source_dataset=c.name, source_version=c.version_note[:120], source_record_id=rid,
                          license_id=c.license.name[:120], license_verified=c.license_verified, origin_verified=c.origin_verified,
                          label_origin="mapped_from_source", mapping_id=self.mapping.mapping_id, mapping_version=self.mapping.version,
                          retrieved_at=self.retrieved_at)

    def resolve(self, path) -> RoleResolution:
        headers = sniff_headers(path)
        res = self.policy.classify_headers(headers, self.role_map)
        need = list(REQUIRED_ROLES) + ([] if self.row_index_ids else ["complaint_id"])
        missing = [r for r in need if r not in res.columns]
        if missing:
            raise SchemaMismatch(f"cannot resolve required role(s) {missing}. Available headers: {sorted(headers)}. Read the dataset's data dictionary "
                                 f"and pass --role-map (column -> role){' or --row-index-ids to use row numbers as ids' if 'complaint_id' in missing else ''}.")
        self.resolution = res
        return res

    def summary(self) -> dict:
        r = self.resolution
        assert r is not None
        return {"resolved_roles": r.columns, "unclassified_columns_default_denied": r.unclassified, "pii_columns_never_read": r.pii_ignored,
                "sensitive_columns_never_stored": r.sensitive_ignored,
                "post_resolution_text_never_stored": [c for role, c in r.columns.items() if role == "resolution_remarks"]}

    # ------------------------------------------------------------------ main iterator
    def iter_records(self, path, *, max_rows: int | None = None, sample_seed: int = 0, since: str | None = None, until: str | None = None) -> Iterator[CaseRecord]:
        res = self.resolve(path)
        cols, roles = res.columns, self.policy.roles
        storable = [n for n, r in roles.items() if n in cols and r.store and not r.derived and r.phase not in NEVER_PHASES and not r.field]
        seen_ids: set[str] = set()

        def get(row, role):
            c = cols.get(role)
            if c is None:
                return None
            v = row.get(c)
            if isinstance(v, str):
                v = v.strip()
                return v or None
            return v

        def gen() -> Iterator[CaseRecord]:
            for i, row in enumerate(iter_rows(path)):
                self.stats["rows_read"] += 1
                rid = get(row, "complaint_id")
                if rid is None and self.row_index_ids:
                    rid = f"row{i}"
                if rid is None:
                    self.stats["dropped_no_id"] += 1
                    continue
                rid = str(rid)
                if rid in seen_ids:
                    self.stats["duplicate_ids"] += 1
                seen_ids.add(rid)
                created = parse_ts(get(row, "created_at"))
                if created is None:
                    self.stats["no_created_at"] += 1
                if (since and (created is None or created[:10] < since)) or (until and (created is None or created[:10] > until)):
                    continue
                src_cat, src_sub = get(row, "source_category"), get(row, "source_subcategory")
                m = self.mapping.map(category=src_cat, subcategory=src_sub)
                self.coverage.add(m, f"{src_cat} | {src_sub}" if src_sub else str(src_cat))
                lat = parse_coord(get(row, "latitude"), -90, 90)
                lon = parse_coord(get(row, "longitude"), -180, 180)
                if lat is None or lon is None or (lat == 0 and lon == 0):
                    lat = lon = None
                    self.stats["no_coordinates"] += 1
                elif not (MUMBAI_BBOX[0] <= lat <= MUMBAI_BBOX[2] and MUMBAI_BBOX[1] <= lon <= MUMBAI_BBOX[3]):
                    self.stats["outside_mumbai_bbox"] += 1
                closed = parse_ts(get(row, "closed_at"))
                attrs = {n: coerce(get(row, n), roles[n].dtype) for n in storable}
                attrs["resolution_hours"] = self._duration_hours(created, closed, get(row, "resolution_duration"))
                text = None
                if self.confirm_citizen_text and "description" in cols:
                    text = get(row, "description")
                dup = coerce(get(row, "duplicate_flag"), "bool") if "duplicate_flag" in cols else None
                parent = get(row, "parent_complaint_id")
                yield CaseRecord(
                    record_id=f"{self.card.id}:{rid}", provenance=self.provenance(rid),
                    text=text, text_origin="citizen_narrative" if text else "none",
                    source_category=str(src_cat) if src_cat else None, source_subcategory=str(src_sub) if src_sub else None,
                    source_agency=str(get(row, "department")) if get(row, "department") is not None else None,
                    category=m.category, subcategory=m.subcategory, department=None,      # never filled from the taxonomy (circular target)
                    mapping_status=m.status, status=str(get(row, "status")) if get(row, "status") is not None else None,
                    created_at=created, closed_at=closed, latitude=lat, longitude=lon,
                    place=str(get(row, "ward")) if get(row, "ward") is not None else None,
                    duplicate_flag=dup, parent_record_id=f"{self.card.id}:{parent}" if parent else None, attributes=attrs)

        n_total = n_bad = 0
        for rec in reservoir(gen(), max_rows, sample_seed):
            yield rec
        n_total = self.stats["rows_read"]
        n_bad = self.stats["no_created_at"]
        if n_total >= 50 and n_bad / n_total > MAX_UNPARSED_DATE_SHARE:
            raise SchemaMismatch(f"{n_bad}/{n_total} rows have an unparseable created_at (column {cols.get('created_at')!r}). Confirm the date "
                                 f"format in the data dictionary and extend columns.parse_ts before trusting any result.")

    def _duration_hours(self, created: str | None, closed: str | None, raw) -> float | None:
        if created and closed:
            h = (datetime.fromisoformat(closed) - datetime.fromisoformat(created)).total_seconds() / 3600.0
            if h < 0:
                self.stats["negative_duration"] += 1
                return None
            return round(h, 3)
        if raw is not None and "resolution_duration" in (self.resolution.columns if self.resolution else {}):
            v = coerce(raw, "float")
            if v is None:
                return None
            if self.resolution_unit is None:
                self.stats["duration_unit_unknown"] += 1
                return None
            return round(v * (24.0 if self.resolution_unit == "days" else 1.0), 3)
        if "closed_at" in (self.resolution.columns if self.resolution else {}) and not closed:
            self.stats["unresolved_no_closed_at"] += 1
        return None
