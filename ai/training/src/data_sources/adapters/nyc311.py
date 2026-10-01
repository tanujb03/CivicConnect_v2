"""NYC 311 Service Requests (Socrata erm2-nwe9) -> CaseRecord.

Column aliases are an UNVERIFIED expectation (egress to the portal was blocked when written). The adapter
fails loudly with the real header list if a required column is missing. Address columns are never read.
No citizen narrative is assumed: ``text`` stays empty unless ``include_category_text`` is set, in which
case it is labelled ``source_category_text`` (label leakage; excluded from classifier evaluation).
"""
from __future__ import annotations

from .base import TabularCaseAdapter


class NYC311Adapter(TabularCaseAdapter):
    source_id = "nyc311"
    aliases = {
        "record_id": ["unique_key", "Unique Key"],
        "created_at": ["created_date", "Created Date"],
        "closed_at": ["closed_date", "Closed Date"],
        "agency": ["agency", "Agency"],
        "complaint_type": ["complaint_type", "Complaint Type"],
        "descriptor": ["descriptor", "Descriptor"],
        "status": ["status", "Status"],
        "latitude": ["latitude", "Latitude"],
        "longitude": ["longitude", "Longitude"],
        "borough": ["borough", "Borough"],
    }
    required = {"record_id", "created_at", "complaint_type"}
    category_field = "complaint_type"
    subcategory_field = "descriptor"
    place_field = "borough"
    agency_field = "agency"
