"""Tabular (311-style) adapter base class."""
from __future__ import annotations

from typing import Iterator

from ..canonical import CaseRecord, Provenance
from ..card_schema import SourceCard
from ..columns import ColumnResolver, iter_rows, parse_bool, parse_coord, parse_ts, reservoir, sniff_headers
from ..mapping import CoverageReport, MappingTable


def _s(v):
    return None if v is None else str(v)


class TabularCaseAdapter:
    source_id: str = ""
    aliases: dict[str, list[str]] = {}
    required: set[str] = set()
    category_field = ""            # canonical field whose value is the source category label
    subcategory_field: str | None = None
    place_field: str | None = None
    agency_field: str | None = None

    def __init__(self, card: SourceCard, mapping: MappingTable, *, retrieved_at: str | None = None,
                 include_category_text: bool = False, exclude_legacy: bool = False):
        self.card, self.mapping = card, mapping
        self.retrieved_at = retrieved_at
        self.include_category_text = include_category_text
        self.exclude_legacy = exclude_legacy
        self.coverage = CoverageReport()
        self.stats = {"rows_read": 0, "dropped_no_id": 0, "dropped_legacy": 0, "no_coordinates": 0, "no_created_at": 0}

    # ---- helpers ---------------------------------------------------------- #
    def provenance(self, record_id: str | None) -> Provenance:
        return Provenance(
            kind="real_public", source_id=self.card.id, source_dataset=self.card.name, source_version=self.card.version_note[:120],
            source_record_id=record_id, license_id=self.card.license.name[:120], license_verified=self.card.license_verified,
            label_origin="mapped_from_source", mapping_id=self.mapping.mapping_id, mapping_version=self.mapping.version,
            retrieved_at=self.retrieved_at)

    def headers(self, path) -> ColumnResolver:
        return ColumnResolver(sniff_headers(path), self.aliases, self.required)

    def extras(self, row: dict, cols: ColumnResolver) -> dict:
        """Source-specific fields (duplicate links etc.); overridden by subclasses."""
        return {}

    def keep(self, row: dict, cols: ColumnResolver) -> bool:
        return True

    # ---- main iterator ------------------------------------------------------ #
    def iter_records(self, path, *, max_rows: int | None = None, sample_seed: int = 0,
                     since: str | None = None, until: str | None = None) -> Iterator[CaseRecord]:
        cols = self.headers(path)

        def gen() -> Iterator[CaseRecord]:
            for row in iter_rows(path):
                self.stats["rows_read"] += 1
                if not self.keep(row, cols):
                    continue
                rid = cols.get(row, "record_id")
                if rid is None:
                    self.stats["dropped_no_id"] += 1
                    continue
                created = parse_ts(cols.get(row, "created_at"))
                if created is None:
                    self.stats["no_created_at"] += 1
                if (since and (created is None or created[:10] < since)) or (until and (created is None or created[:10] > until)):
                    continue
                src_fields = {f: cols.get(row, f) for f in self.mapping.raw["match_fields"]}
                res = self.mapping.map(**src_fields)
                src_cat = cols.get(row, self.category_field)
                src_sub = cols.get(row, self.subcategory_field) if self.subcategory_field else None
                lat = parse_coord(cols.get(row, "latitude"), -90, 90)
                lon = parse_coord(cols.get(row, "longitude"), -180, 180)
                if lat is None or lon is None or (lat == 0 and lon == 0):
                    lat = lon = None
                    self.stats["no_coordinates"] += 1
                text = None
                if self.include_category_text and src_cat:
                    text = f"{src_cat} - {src_sub}" if src_sub else str(src_cat)
                self.coverage.add(res, f"{src_cat} | {src_sub}" if src_sub else str(src_cat))
                yield CaseRecord(
                    record_id=f"{self.card.id}:{rid}", provenance=self.provenance(str(rid)),
                    text=text, text_origin="source_category_text" if text else "none",
                    source_category=str(src_cat) if src_cat else None, source_subcategory=str(src_sub) if src_sub else None,
                    source_agency=_s(cols.get(row, self.agency_field)) if self.agency_field else None,
                    category=res.category, subcategory=res.subcategory, department=self.mapping.department_for(res),
                    mapping_status=res.status, status=_s(cols.get(row, "status")), created_at=created,
                    closed_at=parse_ts(cols.get(row, "closed_at")), latitude=lat, longitude=lon,
                    place=_s(cols.get(row, self.place_field)) if self.place_field else None,
                    **self.extras(row, cols))

        yield from reservoir(gen(), max_rows, sample_seed)


__all__ = ["TabularCaseAdapter", "parse_bool"]
