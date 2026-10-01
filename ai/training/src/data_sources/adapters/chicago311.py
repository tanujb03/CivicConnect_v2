"""Chicago 311 Service Requests (Socrata v6vf-nfxy) -> CaseRecord.

Duplicate/parent columns are optional and resolved by alias because their exact names are UNCONFIRMED.
If they are absent the adapter still works, but no duplicate pairs can be built (``cli profile`` shows
which columns exist). Agency-assigned duplicate flags are kept as ``duplicate_flag`` / ``parent_record_id``.
"""
from __future__ import annotations

from ..columns import ColumnResolver, parse_bool
from .base import TabularCaseAdapter


class Chicago311Adapter(TabularCaseAdapter):
    source_id = "chicago311"
    aliases = {
        "record_id": ["sr_number", "SR_NUMBER", "service_request_number"],
        "created_at": ["created_date", "CREATED_DATE"],
        "closed_at": ["closed_date", "CLOSED_DATE"],
        "sr_type": ["sr_type", "SR_TYPE", "service_request_type"],
        "agency": ["owner_department", "OWNER_DEPARTMENT"],
        "status": ["status", "STATUS"],
        "latitude": ["latitude", "LATITUDE"],
        "longitude": ["longitude", "LONGITUDE"],
        "place": ["community_area", "COMMUNITY_AREA", "ward", "WARD"],
        "duplicate": ["duplicate", "is_duplicate", "isduplicate"],
        "parent": ["parent_sr_number", "parent_service_request_number", "parentservicerequestnumber"],
        "legacy": ["legacy_record", "legacy"],
    }
    required = {"record_id", "created_at", "sr_type"}
    category_field = "sr_type"
    place_field = "place"
    agency_field = "agency"

    def keep(self, row: dict, cols: ColumnResolver) -> bool:
        if self.exclude_legacy and parse_bool(cols.get(row, "legacy")):
            self.stats["dropped_legacy"] += 1
            return False
        return True

    def extras(self, row: dict, cols: ColumnResolver) -> dict:
        parent = cols.get(row, "parent")
        return {"duplicate_flag": parse_bool(cols.get(row, "duplicate")),
                "parent_record_id": f"{self.card.id}:{parent}" if parent else None}
