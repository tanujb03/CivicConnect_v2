"""Column-role policy: which columns of a dataset may be INPUTS or TARGETS for which task (default-deny).

Every column of a structured dataset is assigned to a *role* (explicitly, by alias, or via an operator-supplied
role map). Every task lists the roles it may use as inputs and the roles that are its targets. Anything else —
including every column nobody classified — is unavailable to that task. Roles carry a *phase* (when the
information exists in the workflow):

    identifier / at_submission  known when the citizen files the complaint
    post_triage                 assigned after the report is triaged (department, severity, priority, contractor...)
    post_resolution             events/outcomes after work starts (status, closing time, remarks, reassignment,
                                escalation, SLA breach, reopening, satisfaction...)
    sensitive_attribute         complainant profile attributes: never an input, target or stored value (design §13)
    pii_never_read              names, contacts, addresses, officers: never read at all

Structural rules enforced by :meth:`TaskPolicy.validate` (and tested): inputs never contain targets or forbidden
roles; input phases never exceed the task's ``max_phase``; only ``demo_only`` tasks may touch post-resolution roles;
sensitive/PII roles appear in no task. Post-resolution roles can only be *targets* of descriptive tasks.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .columns import norm_header
from .errors import DataSourceError, SchemaMismatch

POLICY_DIR = Path(__file__).parent / "mappings"
PHASES = ("identifier", "at_submission", "post_triage", "post_resolution", "sensitive_attribute", "pii_never_read")
PHASE_RANK = {"identifier": 0, "at_submission": 0, "post_triage": 1, "post_resolution": 2}
NEVER_PHASES = {"sensitive_attribute", "pii_never_read"}


class LeakageError(DataSourceError):
    """A task tried to use a role it is not allowed to use (leakage / governance violation)."""


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RoleSpec(_M):
    name: str
    phase: Literal["identifier", "at_submission", "post_triage", "post_resolution", "sensitive_attribute", "pii_never_read"]
    aliases: list[str] = Field(default_factory=list)
    field: str | None = None                      # CaseRecord core field holding the value; None => record.attributes[name]
    store: bool = True                            # False: never written to prepared output (still classified, so it is not "unclassified")
    derived: bool = False                         # computed by the adapter (not a source column)
    dtype: Literal["str", "float", "int", "bool"] = "str"
    description: str = ""


class TaskSpec(_M):
    task: str
    capability: str
    status: Literal["supported", "conditional", "demo_only", "not_pursued"]
    purpose: Literal["descriptive", "evaluation", "demo", "none"]
    max_phase: Literal["at_submission", "post_triage", "post_resolution"] = "at_submission"
    inputs: list[str] = Field(default_factory=list)
    targets: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)       # role names or "phase:<phase>"
    requires: list[str] = Field(default_factory=list)        # roles that must be resolvable in the file
    requires_any: list[str] = Field(default_factory=list)
    operator_confirmations: list[str] = Field(default_factory=list)
    leakage_checks: list[str] = Field(default_factory=list)
    track: Literal["synthetic", "real_holdout", "hybrid", "descriptive", "none"] = "descriptive"
    conditions: list[str] = Field(default_factory=list)
    notes: str = ""


class PolicyFile(_M):
    source_id: str
    policy_version: str
    status: str
    notes: list[str] = Field(default_factory=list)
    roles: list[RoleSpec]
    tasks: list[TaskSpec]


@dataclass
class RoleResolution:
    columns: dict[str, str] = field(default_factory=dict)          # role -> source column
    unclassified: list[str] = field(default_factory=list)          # columns no role claims: default-denied everywhere
    pii_ignored: list[str] = field(default_factory=list)
    sensitive_ignored: list[str] = field(default_factory=list)


@dataclass
class TaskView:
    task: str
    inputs: dict[str, Any]
    targets: dict[str, Any]


class TaskPolicy:
    def __init__(self, spec: PolicyFile):
        self.spec = spec
        self.roles = {r.name: r for r in spec.roles}
        self.tasks = {t.task: t for t in spec.tasks}
        self.validate()

    @classmethod
    def from_dict(cls, raw: dict) -> "TaskPolicy":
        return cls(PolicyFile.model_validate(raw))

    @classmethod
    def load(cls, source_id: str, policy_dir: Path = POLICY_DIR) -> "TaskPolicy":
        path = policy_dir / f"{source_id}_columns.v1.json"
        if not path.is_file():
            raise DataSourceError(f"no column-role policy for {source_id!r}: {path}")
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    # ------------------------------------------------------------------ validation
    def effective_forbidden(self, task: str) -> set[str]:
        t = self.tasks[task]
        out: set[str] = set()
        for f in t.forbidden:
            if f.startswith("phase:"):
                ph = f.split(":", 1)[1]
                out |= {r.name for r in self.roles.values() if r.phase == ph}
            else:
                out.add(f)
        out |= {r.name for r in self.roles.values() if r.phase in NEVER_PHASES}
        return out

    def validate(self) -> None:
        if len(self.roles) != len(self.spec.roles) or len(self.tasks) != len(self.spec.tasks):
            raise DataSourceError("duplicate role or task names")
        seen: dict[str, str] = {}
        for r in self.roles.values():
            for a in r.aliases:
                n = norm_header(a)
                if n in seen and seen[n] != r.name:
                    raise DataSourceError(f"alias {a!r} claimed by roles {seen[n]!r} and {r.name!r}")
                seen[n] = r.name
        for t in self.tasks.values():
            unknown = (set(t.inputs) | set(t.targets) | set(t.requires) | set(t.requires_any)) - set(self.roles)
            if unknown:
                raise DataSourceError(f"task {t.task}: unknown roles {sorted(unknown)}")
            if set(t.inputs) & set(t.targets):
                raise LeakageError(f"task {t.task}: a role cannot be both input and target: {sorted(set(t.inputs) & set(t.targets))}")
            forb = self.effective_forbidden(t.task)
            if set(t.inputs) & forb:
                raise LeakageError(f"task {t.task}: inputs overlap forbidden roles {sorted(set(t.inputs) & forb)}")
            if set(t.targets) & {r.name for r in self.roles.values() if r.phase in NEVER_PHASES}:
                raise LeakageError(f"task {t.task}: sensitive/PII roles can never be targets")
            limit = PHASE_RANK[t.max_phase]
            for name in t.inputs:
                ph = self.roles[name].phase
                if ph in NEVER_PHASES or PHASE_RANK[ph] > limit:
                    raise LeakageError(f"task {t.task}: input role {name!r} (phase {ph}) is later than max_phase {t.max_phase}")
            if t.purpose != "demo" and t.max_phase == "post_resolution":
                raise LeakageError(f"task {t.task}: only demo tasks may use post-resolution information as input")
            if t.purpose in ("descriptive", "evaluation"):
                post_res_inputs = [n for n in t.inputs if self.roles[n].phase == "post_resolution"]
                if post_res_inputs:
                    raise LeakageError(f"task {t.task}: post-resolution inputs {post_res_inputs}")
            if t.status == "conditional" and not (t.requires or t.requires_any or t.operator_confirmations):
                raise DataSourceError(f"task {t.task}: conditional tasks must state their conditions")

    # ------------------------------------------------------------------ column classification
    def classify_headers(self, headers: list[str], role_map: dict[str, str] | None = None) -> RoleResolution:
        """Assign columns to roles: explicit operator map first, then unique alias matches. Ambiguity fails loudly."""
        role_map = role_map or {}
        by_norm = {norm_header(h): h for h in headers}
        bad = [r for r in role_map.values() if r not in self.roles]
        if bad:
            raise SchemaMismatch(f"role map names unknown roles {sorted(set(bad))}; known roles: {sorted(self.roles)}")
        missing = [c for c in role_map if c not in headers]
        if missing:
            raise SchemaMismatch(f"role map names columns not in the file: {missing}. Available headers: {sorted(headers)}")
        res = RoleResolution()
        claimed: dict[str, str] = {}
        for col, role in role_map.items():
            if role in res.columns and res.columns[role] != col and self.roles[role].phase not in NEVER_PHASES:
                raise SchemaMismatch(f"role {role!r} assigned to both {res.columns[role]!r} and {col!r}")
            res.columns.setdefault(role, col)
            claimed[col] = role
        for r in self.roles.values():
            if r.derived:
                continue
            never = r.phase in NEVER_PHASES      # sensitive/PII roles span several columns: claim them all (they are ignored anyway)
            if r.name in res.columns and not never:
                continue
            hits = sorted({by_norm[norm_header(a)] for a in r.aliases if norm_header(a) in by_norm} - set(claimed))
            if never:
                for h in hits:
                    res.columns.setdefault(r.name, h)
                    claimed[h] = r.name
                continue
            if len(hits) > 1:
                raise SchemaMismatch(f"role {r.name!r} is ambiguous: columns {hits} all match its aliases. Resolve with --role-map "
                                     f"(e.g. {{\"{hits[0]}\": \"{r.name}\"}}).")
            if hits:
                res.columns[r.name] = hits[0]
                claimed[hits[0]] = r.name
        for col in headers:
            role = claimed.get(col)
            if role is None:
                res.unclassified.append(col)
            elif self.roles[role].phase == "pii_never_read":
                res.pii_ignored.append(col)
            elif self.roles[role].phase == "sensitive_attribute":
                res.sensitive_ignored.append(col)
        return res

    def runnable(self, task: str, resolved_roles: set[str], confirmations: set[str] | None = None) -> tuple[bool, list[str]]:
        t = self.tasks[task]
        why: list[str] = []
        if t.status == "not_pursued":
            why.append("task is not pursued in V1")
        miss = [r for r in t.requires if r not in resolved_roles]
        if miss:
            why.append(f"required roles not resolvable in this file: {miss}")
        if t.requires_any and not (set(t.requires_any) & resolved_roles):
            why.append(f"none of {t.requires_any} is resolvable")
        need = [c for c in t.operator_confirmations if c not in (confirmations or set())]
        if need:
            why.append(f"operator confirmation(s) missing: {need}")
        return (not why), why

    # ------------------------------------------------------------------ task views
    def _value(self, record, role: str):
        spec = self.roles[role]
        if spec.field:
            return getattr(record, spec.field, None)
        return record.attributes.get(role)

    def view(self, record, task: str) -> TaskView:
        """The ONLY sanctioned way to feed a record to a task: returns allowed inputs and targets, nothing else."""
        t = self.tasks[task]
        if t.status == "not_pursued":
            raise LeakageError(f"task {task} is not pursued")
        return TaskView(task, {r: self._value(record, r) for r in t.inputs}, {r: self._value(record, r) for r in t.targets})

    def read(self, record, task: str, role: str):
        """Read one role for a task, raising LeakageError if the task may not see it (as an input or target)."""
        t = self.tasks[task]
        if role in self.effective_forbidden(task) or (role not in t.inputs and role not in t.targets):
            raise LeakageError(f"task {task} may not read role {role!r} (default-deny)")
        return self._value(record, role)

    def allowed_roles(self, task: str) -> tuple[list[str], list[str]]:
        t = self.tasks[task]
        return list(t.inputs), list(t.targets)


def parse_bool_value(v) -> bool | None:
    if v is None:
        return None
    s = str(v).strip().casefold()
    if s in {"true", "t", "1", "yes", "y"}:
        return True
    if s in {"false", "f", "0", "no", "n"}:
        return False
    return None


def coerce(value, dtype: str):
    if value is None or value == "":
        return None
    try:
        if dtype == "float":
            return float(value)
        if dtype == "int":
            return int(float(value))
        if dtype == "bool":
            return parse_bool_value(value)
    except (TypeError, ValueError):
        return None
    return str(value)

