"""Response shapes of the analytics endpoints the admin and overlooker apps chart (trends, department performance, ward heatmap)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TrendPoint(BaseModel):
    bucket: str = Field(description="YYYY-MM-DD (UTC): the day, or the Monday of the week")
    category: str
    status: str
    count: int


class TrendTotal(BaseModel):
    bucket: str
    created: int
    resolved: int
    critical: int


class TrendsOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    granularity: Literal["daily", "weekly"]
    from_: str = Field(alias="from")
    until: str
    scope: str
    series: list[TrendPoint]
    totals: list[TrendTotal]


class SeverityCount(BaseModel):
    severity: str
    count: int


class DepartmentStatsOut(BaseModel):
    department_id: str
    name: str
    days: int
    incoming: int
    active: int
    resolved: int
    median_resolution_hours: float
    sla_compliance_pct: float
    reopened: int
    backlog_age_days: float
    recurring_cases: int
    by_severity: list[SeverityCount]


class DepartmentStatsList(BaseModel):
    items: list[DepartmentStatsOut]


class CategoryCount(BaseModel):
    category: str
    count: int


class WardStatsOut(BaseModel):
    ward_id: str
    label: str
    name: str
    cases: int
    open: int
    sla_breached: int
    reopened: int
    critical: int
    backlog: int
    median_resolution_days: float
    recurrence: int
    by_category: list[CategoryCount]


class WardStatsList(BaseModel):
    items: list[WardStatsOut]
