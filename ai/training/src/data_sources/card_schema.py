"""Dataset *source cards*: the machine-readable provenance/licence record for every dataset.

A card is the single place that records source URL, version, licence/terms, attribution,
the subset used, intended use, restrictions and which AI capabilities the data can (and
cannot) legitimately support. Downloads and preparation are gated on it.

Evidence discipline: every licence statement carries its *reliability*:
``primary`` (read from the official page by a human/tool), ``secondary`` (web-search summary,
third-party page) or ``recalled`` (from memory). Anything not ``primary`` leaves the licence
``UNVERIFIED`` and requires an explicit operator acknowledgement before use.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .errors import DataSourceError, TermsNotAccepted

CARDS_DIR = Path(__file__).parent / "cards"

Capability = Literal["AI-1", "AI-2", "AI-3", "AI-4", "AI-5", "AI-6"]
Priority = Literal["primary", "secondary", "optional", "future"]
OriginStatus = Literal["PUBLISHER_IDENTIFIED", "UNVERIFIED_ORIGIN"]   # UNVERIFIED_ORIGIN: unclear whether rows are real, simulated or derived
IdentityStatus = Literal["CONFIRMED_BY_USER", "CONFIRMED_PUBLISHED_REFERENCE", "CANDIDATE_NEEDS_CONFIRMATION"]
Reliability = Literal["primary", "secondary", "recalled"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(_M):
    source: str
    reliability: Reliability
    note: str
    retrieved_on: str | None = None


class LicenseInfo(_M):
    name: str
    url: str | None = None
    status: Literal["VERIFIED_PRIMARY", "UNVERIFIED"]
    verified_on: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    attribution: str
    share_alike: bool | None = None
    commercial_use: str = "unverified"
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _verified_needs_primary_evidence(self) -> "LicenseInfo":
        if self.status == "VERIFIED_PRIMARY" and not (self.verified_on and any(e.reliability == "primary" for e in self.evidence)):
            raise ValueError("a VERIFIED_PRIMARY licence needs verified_on and at least one primary-reliability evidence entry")
        return self


class CapabilityUse(_M):
    capability: Capability
    how: str
    caveats: list[str] = Field(default_factory=list)


class CapabilityGap(_M):
    capability: str
    why: str


class SourceCard(_M):
    id: str
    name: str
    kind: Literal["real_public", "synthetic"]
    publisher: str
    landing_url: str | None = None
    official_source_url: str | None = None
    version_note: str
    data_access: dict[str, str] = Field(default_factory=dict)
    license: LicenseInfo
    subset_used: str
    intended_use: list[Literal["training", "evaluation", "calibration", "demo", "analytics_validation"]]
    restrictions: list[str] = Field(default_factory=list)
    redistribution_in_git: Literal["never"] = "never"   # raw AND prepared real data are never committed
    supports: list[CapabilityUse] = Field(default_factory=list)
    does_not_support: list[CapabilityGap] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)
    privacy_notes: list[str] = Field(default_factory=list)
    expected_schema_notes: list[str] = Field(default_factory=list)
    adapter: str | None = None
    mapping_id: str | None = None
    priority: Priority = "secondary"
    role_summary: str | None = None
    identity_status: IdentityStatus = "CONFIRMED_PUBLISHED_REFERENCE"
    reference: str | None = None             # exact identifier as supplied (e.g. a Kaggle slug / DOI); not guessed
    origin_status: OriginStatus = "PUBLISHER_IDENTIFIED"
    origin_notes: list[str] = Field(default_factory=list)
    related_sources: list[str] = Field(default_factory=list)
    citation: str | None = None
    last_reviewed: str
    review_status: Literal["DRAFT_NEEDS_HUMAN_REVIEW", "REVIEWED"] = "DRAFT_NEEDS_HUMAN_REVIEW"

    @property
    def license_verified(self) -> bool:
        return self.license.status == "VERIFIED_PRIMARY"

    @property
    def origin_verified(self) -> bool:
        """False when it is unclear whether the rows are real records (vs simulated/derived)."""
        return self.origin_status == "PUBLISHER_IDENTIFIED"

    @model_validator(mode="after")
    def _origin_notes_required(self) -> "SourceCard":
        if self.origin_status == "UNVERIFIED_ORIGIN" and not self.origin_notes:
            raise ValueError("UNVERIFIED_ORIGIN requires origin_notes explaining the uncertainty")
        return self

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True).encode()).hexdigest()

    def terms_summary(self) -> str:
        lic = self.license
        lines = [f"Dataset : {self.name} [{self.id}]", f"Publisher: {self.publisher}",
                 f"Licence : {lic.name}  ({lic.url or 'no URL recorded'})  status={lic.status}",
                 f"Attribution: {lic.attribution}"]
        if lic.share_alike:
            lines.append("Share-alike: derivatives must be shared under the same licence.")
        lines += [f"CONFLICT: {c}" for c in lic.conflicts]
        if self.identity_status == "CANDIDATE_NEEDS_CONFIRMATION":
            lines.append("IDENTITY: this card is a CANDIDATE match for the dataset you described; confirm it is the intended dataset.")
        if not self.origin_verified:
            lines += [f"ORIGIN UNVERIFIED: {n}" for n in self.origin_notes]
        lines += [f"Restriction: {r}" for r in self.restrictions]
        lines.append("Raw and prepared data must NOT be committed to git or redistributed from this repository.")
        return "\n".join(lines)


def load_card(source_id: str, cards_dir: Path = CARDS_DIR) -> SourceCard:
    path = cards_dir / f"{source_id}.json"
    if not path.is_file():
        raise DataSourceError(f"no source card for {source_id!r} in {cards_dir}")
    return SourceCard.model_validate_json(path.read_text(encoding="utf-8"))


def list_cards(cards_dir: Path = CARDS_DIR) -> list[SourceCard]:
    return [SourceCard.model_validate_json(p.read_text(encoding="utf-8")) for p in sorted(cards_dir.glob("*.json"))]


def check_terms(card: SourceCard, *, accepted: list[str], ack_unverified: bool) -> None:
    """Gate for download/prepare. The operator must name the dataset they accept the terms of, and
    must separately acknowledge when the licence has not been verified at the primary source."""
    if card.kind == "synthetic":
        return
    if card.id not in accepted:
        raise TermsNotAccepted(
            f"Review the terms and re-run with --accept-terms {card.id}\n\n{card.terms_summary()}")
    if not card.license_verified and not ack_unverified:
        raise TermsNotAccepted(
            f"The licence for {card.id} is UNVERIFIED (see the card's evidence/conflicts). Verify it at the "
            f"official source, update the card (status=VERIFIED_PRIMARY), or pass --acknowledge-unverified-license "
            f"to proceed locally (outputs will be flagged license_verified=false and results must not be published).\n\n"
            f"{card.terms_summary()}")
