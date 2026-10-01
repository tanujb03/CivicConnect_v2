"""Whitelisted, read-only copilot tools (AI-6).

The model can only *request* these tools with validated arguments. There is no
free-form SQL, no table/column names, no credentials: the backend's
``ToolExecutor`` maps each tool to parameterised, RBAC-checked queries.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ..provider import ToolSpec
from ..schemas import ActorContext, Citation, CopilotScope, Priority, Severity

CaseStatus = Literal[
    "SUBMITTED", "AI_PROCESSING", "NEEDS_REVIEW", "ASSIGNED", "WORK_ORDER_CREATED", "IN_PROGRESS",
    "RESOLUTION_SUBMITTED", "AWAITING_VERIFICATION", "VERIFIED", "RESOLVED", "REOPENED", "REJECTED",
]


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseFilters(_Args):
    category: str | None = Field(default=None, description="Category id, e.g. 'sanitation'")
    subcategory: str | None = None
    status: list[CaseStatus] | None = None
    unresolved_only: bool = Field(default=False, description="Exclude VERIFIED/RESOLVED/REJECTED cases")
    severity: list[Severity] | None = None
    priority: list[Priority] | None = None
    ward_id: str | None = None
    ward_label: str | None = Field(default=None, description="Ward label as the admin wrote it, e.g. 'W18'")
    department_id: str | None = None
    older_than_days: int | None = Field(default=None, ge=0, le=3650)
    created_from: datetime | None = None
    created_until: datetime | None = None


class SearchCasesArgs(CaseFilters):
    sort: Literal["priority", "age", "support"] = "priority"
    limit: int = Field(default=20, ge=1, le=200)


class CountCasesArgs(CaseFilters):
    group_by: Literal["category", "status", "severity", "priority", "ward", "department"]


class GetAnalyticArgs(_Args):
    name: Literal["overview", "hotspots", "recurrence", "department_performance", "ward_comparison"]
    ward_id: str | None = None
    department_id: str | None = None
    period_days: int = Field(default=30, ge=1, le=365)


TOOL_MODELS: dict[str, type[_Args]] = {
    "search_cases": SearchCasesArgs,
    "count_cases": CountCasesArgs,
    "get_analytic": GetAnalyticArgs,
}

_DESCRIPTIONS = {
    "search_cases": "List civic cases matching filters (read-only). Use for 'show me ...' questions.",
    "count_cases": "Count civic cases matching filters, grouped by one field (read-only).",
    "get_analytic": "Fetch a pre-computed analytic (overview, hotspots, recurrence, department performance, ward comparison).",
}


def tool_specs() -> list[ToolSpec]:
    return [ToolSpec(name=n, description=_DESCRIPTIONS[n], parameters=m.model_json_schema())
            for n, m in TOOL_MODELS.items()]


@dataclass
class ToolResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    truncated: bool = False


class ToolExecutor(Protocol):
    """Implemented by the backend. Must enforce RBAC for ``actor`` and ``scope``,
    use parameterised queries, and never expose raw credentials to this layer."""

    def execute(self, tool: str, arguments: BaseModel, *, scope: CopilotScope, actor: ActorContext) -> ToolResult: ...
