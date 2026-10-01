"""Configuration loading: taxonomy, policy files and provider settings.

Model IDs are *configuration* (system design Sections 30 and 64): nothing here
hard-codes a model name. They must be validated against the provider's current
model catalogue at implementation kickoff.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, SecretStr

from .errors import TaxonomyError

CONFIG_DIR = Path(__file__).parent / "config"
TAXONOMY_FILE = "taxonomy.v1.json"
TRIAGE_RULES_FILE = "triage_rules.v1.json"
FUSION_POLICY_FILE = "fusion_policy.v1.json"
AI_POLICY_FILE = "ai_policy.v1.json"

SUPPORTED_LANGUAGES = ("en", "hi", "mr", "hi-Latn")


def _load_json(name: str) -> dict[str, Any]:
    with (CONFIG_DIR / name).open(encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- #
# Taxonomy
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Subcategory:
    id: str
    category_id: str
    label: dict[str, str]
    base_severity: str
    safety_critical: bool
    department_id: str | None  # resolved (own override or category default)


@dataclass(frozen=True)
class Category:
    id: str
    label: dict[str, str]
    department_id: str | None
    subcategory_ids: tuple[str, ...]


@dataclass(frozen=True)
class Department:
    id: str
    code: str
    label: dict[str, str]
    category_ids: tuple[str, ...]


@dataclass
class Taxonomy:
    """Read-only view over ``taxonomy.v1.json`` with validation and lookups."""

    raw: dict[str, Any]
    version: str = ""
    status: str = ""
    categories: dict[str, Category] = field(default_factory=dict)
    subcategories: dict[str, Subcategory] = field(default_factory=dict)
    departments: dict[str, Department] = field(default_factory=dict)
    severity_rank: dict[str, int] = field(default_factory=dict)
    priority_rank: dict[str, int] = field(default_factory=dict)
    priority_sla_class: dict[str, str] = field(default_factory=dict)
    sla_hours: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Taxonomy":
        t = cls(raw=raw, version=raw["taxonomy_version"], status=raw.get("status", ""))
        t.severity_rank = {s["id"]: s["rank"] for s in raw["severities"]}
        t.sla_hours = {s["id"]: s["hours"] for s in raw["sla_classes"]}
        t.priority_rank = {p["id"]: p["rank"] for p in raw["priorities"]}
        t.priority_sla_class = {p["id"]: p["default_sla_class"] for p in raw["priorities"]}
        for d in raw["departments"]:
            t.departments[d["id"]] = Department(d["id"], d["code"], d["label"], tuple(d["category_ids"]))
        for c in raw["categories"]:
            t.categories[c["id"]] = Category(
                c["id"], c["label"], c["department_id"], tuple(s["id"] for s in c["subcategories"])
            )
            for s in c["subcategories"]:
                if s["id"] in t.subcategories:
                    raise TaxonomyError(f"duplicate subcategory id: {s['id']}")
                t.subcategories[s["id"]] = Subcategory(
                    s["id"], c["id"], s["label"], s["base_severity"], s["safety_critical"],
                    s.get("department_id") or c["department_id"],
                )
        t.validate()
        return t

    # ---- validation (also exercised by tests) ---------------------------- #
    def validate(self) -> None:
        for p, sla in self.priority_sla_class.items():
            if sla not in self.sla_hours:
                raise TaxonomyError(f"priority {p} references unknown SLA class {sla}")
        for c in self.categories.values():
            if c.department_id and c.department_id not in self.departments:
                raise TaxonomyError(f"category {c.id} references unknown department {c.department_id}")
        for s in self.subcategories.values():
            if s.base_severity not in self.severity_rank:
                raise TaxonomyError(f"subcategory {s.id} has unknown severity {s.base_severity}")
            if s.department_id and s.department_id not in self.departments:
                raise TaxonomyError(f"subcategory {s.id} references unknown department {s.department_id}")

    # ---- lookups ---------------------------------------------------------- #
    @property
    def label_ids(self) -> list[str]:
        """Composite ``category/subcategory`` label IDs in stable order."""
        return [f"{s.category_id}/{s.id}" for s in self.subcategories.values()]

    def is_valid_pair(self, category: str, subcategory: str) -> bool:
        sub = self.subcategories.get(subcategory)
        return sub is not None and sub.category_id == category

    def department_for(self, category: str, subcategory: str | None = None) -> str | None:
        if subcategory and subcategory in self.subcategories:
            return self.subcategories[subcategory].department_id
        cat = self.categories.get(category)
        return cat.department_id if cat else None

    def resolve_department(self, value: str | None) -> str | None:
        """Accepts a canonical ID or an alias/code (e.g. ``WATER``) -> canonical ID."""
        if not value:
            return None
        if value in self.departments:
            return value
        alias = self.raw.get("aliases", {}).get("departments", {})
        return alias.get(value) or alias.get(value.upper())

    def resolve_category(self, value: str | None) -> str | None:
        if not value:
            return None
        v = value.strip().lower()
        if v in self.categories:
            return v
        return self.raw.get("aliases", {}).get("categories", {}).get(v)

    def label(self, kind: str, id_: str, lang: str = "en") -> str:
        table = {"category": self.categories, "subcategory": self.subcategories,
                 "department": self.departments}[kind]
        entry = table.get(id_)
        return entry.label.get(lang) or entry.label["en"] if entry else id_

    def max_severity(self, a: str, b: str) -> str:
        return a if self.severity_rank[a] >= self.severity_rank[b] else b

    def severity_by_rank(self, rank: int) -> str:
        rank = max(1, min(rank, max(self.severity_rank.values())))
        return next(k for k, v in self.severity_rank.items() if v == rank)


@lru_cache(maxsize=1)
def load_taxonomy() -> Taxonomy:
    return Taxonomy.from_dict(_load_json(TAXONOMY_FILE))


# --------------------------------------------------------------------------- #
# Policy / rules files
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def load_triage_rules() -> dict[str, Any]:
    return _load_json(TRIAGE_RULES_FILE)


@lru_cache(maxsize=1)
def load_fusion_policy() -> dict[str, Any]:
    return _load_json(FUSION_POLICY_FILE)


class AIPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")
    intake: dict[str, Any]
    triage: dict[str, Any]
    resolution: dict[str, Any]
    provider: dict[str, Any]
    copilot: dict[str, Any]
    policy_version: str = ""

    @classmethod
    def load(cls) -> "AIPolicy":
        return cls(**_load_json(AI_POLICY_FILE))


# --------------------------------------------------------------------------- #
# Provider settings (environment)
# --------------------------------------------------------------------------- #
# Per-task model resolution: explicit var first, then documented fallbacks.
_MODEL_ENV = {
    "intake": ("AI_INTAKE_MODEL",),
    "triage": ("AI_TRIAGE_MODEL", "AI_INTAKE_MODEL"),
    "resolution": ("AI_RESOLUTION_MODEL", "AI_INTAKE_MODEL"),
    "analytics": ("AI_ANALYTICS_MODEL",),
    "copilot": ("AI_COPILOT_MODEL", "AI_ANALYTICS_MODEL"),
    "embedding": ("AI_EMBEDDING_MODEL",),
    "transcription": ("AI_TRANSCRIPTION_MODEL",),
}


class ProviderSettings(BaseModel):
    """Environment-driven provider settings. Secrets are never printed."""

    model_config = ConfigDict(extra="forbid")

    provider: str = "none"                 # AI_PROVIDER: "openai" | "none"
    api_key: SecretStr | None = None       # OPENAI_API_KEY
    base_url: str = "https://api.openai.com/v1"
    models: dict[str, str] = {}            # task -> model ID (all from env, none hard-coded)
    timeout_s: float = 30.0
    max_retries: int = 1

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "ProviderSettings":
        env = dict(os.environ if env is None else env)
        models: dict[str, str] = {}
        for task, names in _MODEL_ENV.items():
            for n in names:
                if env.get(n):
                    models[task] = env[n]
                    break
        key = env.get("OPENAI_API_KEY")
        provider = env.get("AI_PROVIDER", "openai" if key else "none").lower()
        return cls(
            provider=provider,
            api_key=SecretStr(key) if key else None,
            base_url=env.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            models=models,
            timeout_s=float(env.get("AI_REQUEST_TIMEOUT_S", "30")),
            max_retries=int(env.get("AI_MAX_RETRIES", "1")),
        )

    def model_for(self, task: str) -> str | None:
        return self.models.get(task)
