---
name: add-endpoint
description: Checklist for adding a new FastAPI endpoint to the CivicConnect backend (router, service, schema, permissions, idempotency, errors, audit, tests, docs). Use whenever a work package adds or changes a route under backend/api/v1.
---

# Add an endpoint (CivicConnect backend)

Work through these in order. A sub-agent stops at step 10; the parent does steps 10 and 11.

1. **Contract first.** Method, path under `/api/v1`, request and response shapes, error codes. Shapes live in `backend/schemas/*` (new schema files are fine; `backend/schemas/platform.py` is a shared file, so propose edits to it instead of making them).
2. **Router** in `backend/api/v1/<name>.py` with `router = APIRouter()`. Follow `backend/api/v1/work_orders.py`: `response_model`, `status_code`, `Depends(get_db)`, `Depends(current_user)`; list routes return `Page[...]` with `cursor` and `limit`.
3. **Service function** in `backend/services/<name>.py`. Routers stay thin; all rules and queries live in the service.
4. **Permissions.** Role gate with `require_capability(...)`, `require_staff` or `require_role_in(...)` from `backend.core.permissions`, **plus an object-level check** (the case, work order or user must be visible to the caller: reuse `case_service.get_visible_case` and the `get_visible` helpers). Never trust ids from the path alone. Wrong ward or department answers 403 or 404 like the existing routes.
5. **Idempotency** for every mutation: `idempotency_key: Optional[str] = IdempotencyHeader` and `idempotent(db, response, user_id=..., key=..., method=..., path=..., payload=body.model_dump(mode="json"), handler=handler)` from `backend.api.deps`. Pass `required=False` only for deliberate exceptions and say why in the docstring (`POST /admin/users` ignores the key on purpose).
6. **Errors** raise `CivicConnectException(code, message, status, details)`; add a new code to `backend/core/exceptions.py` only when needed (that file is shared with WP3; propose the edit if you do not own it). Never return raw exception text.
7. **Audit and timeline.** Call `record_audit(db, actor_id=..., action="<entity>.<verb>", entity_type=..., entity_id=..., before=..., after=...)` for state changes; add a case timeline event when the case history should show it. Never put passwords, tokens or keys in audit payloads.
8. **Notifications / events** only through the existing publisher and notification service; failures there must never break the request.
9. **Tests** in `backend/tests/test_api_<name>.py` (SQLite/fakes): success, validation error, every role (citizen, other citizen, field worker, operator, ward officer, admin), wrong ward or department, unauthenticated (401), idempotent replay, audit row written, no secret in the response or audit.
10. **Docs.** Add an entry to `docs/FRONTEND_API_NEEDS.md` (shape, errors, roles). Report router registration needed in `backend/main.py` (parent registers it).
11. **Parent only:** register the router in `backend/main.py`, regenerate `backend/openapi.json` (`python -m backend.scripts.generate_openapi`), run the quality-gates skill, add a `docs/V1_CHANGE_LOG.md` entry if the contract is not purely additive.
