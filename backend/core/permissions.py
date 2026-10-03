"""Role vocabulary and the §51A.18 matrix as code."""
from __future__ import annotations

from fastapi import Depends

from backend.core.exceptions import CivicConnectException
from backend.core.security import current_user

STAFF_ROLES = frozenset({"operator", "department_manager", "ward_officer", "city_admin", "system_admin"})        # the "Admin" column of §51A.18
CITY_WIDE_ROLES = frozenset({"city_admin", "system_admin"})
DEPARTMENT_ROLES = frozenset({"operator", "department_manager"})
ALL_ROLES = STAFF_ROLES | {"citizen", "field_worker", "overlooker"}

# capability -> roles (design §51A.18)
CAPABILITIES: dict[str, frozenset[str]] = {
    "create_case": STAFF_ROLES | {"citizen", "field_worker"},
    "triage_decision": STAFF_ROLES,
    "create_work_order": STAFF_ROLES,
    "submit_resolution": STAFF_ROLES | {"field_worker"},
    "verify_resolution": STAFF_ROLES | {"citizen"},
    "view_analytics": STAFF_ROLES | {"overlooker"},
    "manage_incidents": frozenset({"ward_officer", "city_admin", "system_admin"}),
    "view_incidents": STAFF_ROLES | {"overlooker"},
    "manage_users": frozenset({"city_admin", "system_admin"}),
    "view_map": ALL_ROLES,
}


def forbidden(message: str = "Your role may not do this.", **details) -> CivicConnectException:
    return CivicConnectException("AUTH_FORBIDDEN", message, 403, details)


def require_capability(name: str):
    allowed = CAPABILITIES[name]

    def _dep(user=Depends(current_user)):
        if user.role not in allowed:
            raise forbidden(capability=name)
        return user
    return _dep


def require_role_in(*roles: str):
    allowed = frozenset(roles)

    def _dep(user=Depends(current_user)):
        if user.role not in allowed:
            raise forbidden()
        return user
    return _dep


require_staff = require_role_in(*STAFF_ROLES)
