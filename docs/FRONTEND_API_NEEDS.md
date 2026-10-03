# Frontend API needs (lane C1)

What the three frontends need from the backend, read from `apps/admin`, `apps/overlooker`, `apps/citizen` (mock data and prototype pages) and design §51A / A07 / A09 / A12 / A13, and the exact shapes the backend now serves.
All paths are under `/api/v1`. Conventions that do not change: `Authorization: Bearer <access_token>`, mutations accept `Idempotency-Key`, errors are
`{"error": {"code", "message", "details", "request_id"}}`, lists are `{"items": [...], "next_cursor": "..." | null}`, roles are upper case (`CITY_ADMIN`).
Endpoints marked **existing** were already there; **new** / **extended** are this lane's work (additive: no existing field changed meaning except where noted).

## 1. What each page needs

| Page / app | Needs | Served by |
|---|---|---|
| Admin A07 Department Performance (`pages/DepartmentPerformancePage.tsx`) | department list (real ids and names, not the mock `roads`, `electrical`...), per department: incoming (30d), active, resolved (30d), median resolution hours, SLA compliance %, reopened, backlog age days, **workload by severity**, recurring cases | `GET /reference/departments` (new), `GET /analytics/departments/{id}` (extended) |
| Admin A07 cross-department radar | the same numbers for every department in one call | `GET /analytics/departments` (extended) |
| Admin A09 Ward Heatmap (`pages/WardHeatmapPage.tsx`) | per ward: id, name, total cases, critical, average resolution (days), backlog, recurring locations, **category distribution**; ward list with geometry for a map | `GET /analytics/wards` (extended), `GET /reference/wards?include=boundary` (new) |
| Admin A12 User Management (`components/UserManagementPage.tsx`; prototype with mock citizens/admins) | list and search users (name, email, phone, role, department, ward, active, registered, last login, reports submitted), create staff, change role/department/ward, deactivate/reactivate | `GET/POST /admin/users`, `PATCH /admin/users/{id}` (new) |
| Admin A13 System Settings (`components/SystemSettingsPage.tsx`; prototype) | notification toggles (email, SMS, push, escalation emails), SLA targets, plus the AI and duplicate thresholds, languages, flag review threshold | `GET/PUT /admin/settings` (new) |
| Admin analytics / dashboard | trend by category and status | `GET /analytics/trends` (new); `GET /analytics/overview` (**existing**, extended with `priority_distribution`) |
| Overlooker Analytics (`pages/AnalyticsPage.tsx`) | KPI cards, monthly/weekly trend (submitted, resolved), priority breakdown | `GET /analytics/overview`, `GET /analytics/trends?granularity=weekly` |
| Overlooker City Situation (`pages/CitySituationPage.tsx`) | 7-day new / resolved / critical per day, ward case counts | `GET /analytics/trends?days=7` (`totals`), `GET /analytics/wards` |
| Citizen app | category + subcategory lists for the report form and filters, department names, ward names, notifications, nearby cases | `GET /reference/taxonomy`, `/reference/departments`, `/reference/wards`; `GET /me/notifications` and `GET /map/cases?bbox=` (**existing**) |

### Not provided (no data source in the backend; say so before building UI on it)
- Overlooker KPI cards "Citizen Satisfaction", "Response Rate", "Escalation Rate": nothing records them.
- Citizen "news / city alerts" feed (`mockNews`): no such resource.
- Admin A12 statuses `suspended` / `blocked` and per-user permission lists: users are `active` or `inactive`; permissions follow from the role (`GET /me` returns `access_scope.capabilities`).
- Admin A12 "reset password" and the staff first-login password change: there is **no** password reset or change endpoint yet (only the one-time password returned by `POST /admin/users`).
- Admin A13 departments / categories / branding editors: `PUT /admin/settings` only covers the typed keys below; the taxonomy is read-only (`/reference/taxonomy`).

## 2. Reference data (any authenticated user)

All three: `ETag` (strong, content hash), `Cache-Control: private, max-age=300`. Send `If-None-Match: <etag>` to get `304 Not Modified` with an empty body. 401 without a token.

`GET /reference/taxonomy` (categories and subcategories exactly as in `ai/inference/config/taxonomy.v1.json`; reviewer notes and id conventions are left out)
```json
{"version": "1.0.0-draft", "status": "DRAFT_REQUIRES_REVIEW", "supported_languages": ["en", "hi", "mr", "hi-Latn"],
 "severities": [{"id": "LOW", "rank": 1, "label": {"en": "Low", "hi": "..", "mr": ".."}, "description": ".."}],
 "priorities": [{"id": "LOW", "rank": 1, "default_sla_class": "ROUTINE", "label": {"en": "Low"}}],
 "sla_classes": [{"id": "EMERGENCY", "hours": 4, "label": {"en": "Emergency"}}],
 "departments": [{"id": "road_maintenance", "code": "ROADS", "label": {"en": "Road Maintenance"}, "category_ids": ["roads"]}],
 "categories": [{"id": "roads", "label": {"en": "Roads & Footpaths"}, "department_id": "road_maintenance",
                 "subcategories": [{"id": "pothole", "label": {"en": "Pothole"}, "base_severity": "MEDIUM", "safety_critical": false, "department_id": "road_maintenance"}]}]}
```
`GET /reference/departments` -> `{"items": [{"id": "road_maintenance", "code": "ROADS", "name": "Road Maintenance", "description": null, "name_i18n": {"hi": ".."}, "category_coverage": ["roads"]}]}`

`GET /reference/wards` -> `{"items": [{"id", "label": "W01", "name", "centroid": {"latitude", "longitude"} | null, "bbox": [min_lon, min_lat, max_lon, max_lat] | null}]}`;
with `?include=boundary` every item also has `"boundary"` (GeoJSON Polygon or null). `bbox` is computed from the boundary (null without one).

## 3. User management (CITY_ADMIN, SYSTEM_ADMIN)

Everyone else: 403 `AUTH_FORBIDDEN`. User object (`UserAdminOut`):
```json
{"id", "name", "email", "phone", "role": "OPERATOR", "department_id", "ward_id", "preferred_language", "is_active": true, "status": "active",
 "synthetic": false, "created_at", "updated_at", "last_login_at", "cases_reported": 0}
```
`GET /admin/users?role=&department_id=&ward_id=&is_active=&q=&cursor=&limit=` -> `{"items": [UserAdminOut], "next_cursor"}`. `q` matches name, email and phone (case-insensitive substring); newest first; `limit` 1..100 (default 25).

`POST /admin/users` -> 201 `{"user": UserAdminOut, "temporary_password": "..."}` (the password is shown **once**; only its hash is stored)
```json
{"name": "Ravi Sharma", "email": "ravi@example.gov", "phone": null, "role": "DEPARTMENT_MANAGER", "department_id": "road_maintenance", "ward_id": null, "preferred_language": "en"}
```
Rules: email or phone required; role is one of FIELD_WORKER, OPERATOR, DEPARTMENT_MANAGER, WARD_OFFICER, OVERLOOKER, CITY_ADMIN, SYSTEM_ADMIN (citizens register themselves); OPERATOR / DEPARTMENT_MANAGER / FIELD_WORKER need a valid `department_id`, WARD_OFFICER needs a valid `ward_id`, other roles must not carry either (422 `VALIDATION_ERROR`); duplicate email/phone is 409 `USER_ALREADY_EXISTS`.

`PATCH /admin/users/{id}` -> `UserAdminOut`; body fields are all optional: `{"name", "role", "department_id", "ward_id", "is_active"}` (send `null` to clear a department or ward). The resulting role / department / ward combination is validated as above.
Elevated roles (CITY_ADMIN, SYSTEM_ADMIN; the design's SUPER_ADMIN is the code's SYSTEM_ADMIN): only SYSTEM_ADMIN may grant them or change/deactivate a user who has one (403 `AUTH_FORBIDDEN`).
Nobody can change their own role or deactivate themselves (409 `CANNOT_MODIFY_SELF`). Deactivating a user ends every session at once: access tokens are rejected (401) from the next request, refresh tokens are revoked, push device tokens are revoked. Unknown id: 404 `USER_NOT_FOUND`.
Every change writes `AuditEvent` rows with before/after (`user.created`, `user.role_changed`, `user.deactivated`, `user.reactivated`, `user.updated`); passwords are never written to them.

## 4. System settings (CITY_ADMIN, SYSTEM_ADMIN)

`GET /admin/settings` -> `{"items": [{"key", "value", "default", "is_default", "description", "updated_by", "updated_at"}]}` (all six keys, defaults filled in)
`PUT /admin/settings` body `{"values": {"<key>": <value>, ...}, "reason": "optional text"}` -> same body as GET. All values are validated first; one bad value changes nothing (422 `VALIDATION_ERROR`, `details.errors[] = {key, message}`; unknown key is also 422). Only keys whose value actually changed are written and audited (`settings.updated`, entity id = key, before/after).

| key | value | default | effect |
|---|---|---|---|
| `ai_confidence_threshold` | number 0..1 | 0.55 | **applied**: below it, AI intake proposals carry the low-confidence warning and the local image model may take over |
| `duplicate_threshold` | number 0.5..1 | 0.8 | **applied**: fusion similarity at or above it is `POSSIBLE_DUPLICATE` (below, down to 0.5, is `RELATED`) |
| `sla_hours_by_priority` | `{"LOW": 168, "NORMAL": 72, "HIGH": 48, "URGENT": 24, "CRITICAL": 4}` (all five, hours 1..8760) | taxonomy SLA hours | stored and returned (case SLA is still computed from the taxonomy) |
| `supported_languages` | list of language codes, must contain `"en"`, at most 20 | `["en", "hi", "mr", "hi-Latn"]` | stored and returned |
| `notification_policy` | `{"email": bool, "sms": bool, "push": bool, "escalation_emails": bool}` | push only (no free email/SMS provider) | stored and returned |
| `flag_review_threshold` | integer 1..100 | 3 | stored and returned (open citizen flags that trigger review) |

Changes reach the AI services within 5 seconds in every process (immediately in the process that handled the PUT).

## 5. Analytics

`GET /analytics/trends?granularity=daily|weekly&days=30&category=` (capability `view_analytics`; staff see their scope, the overlooker the whole city; `days` 7..365, default 30; weekly buckets start on Monday)
```json
{"granularity": "daily", "from": "2026-09-05", "until": "2026-10-04", "scope": "city",
 "series": [{"bucket": "2026-10-03", "category": "roads", "status": "RESOLVED", "count": 4}],
 "totals": [{"bucket": "2026-10-03", "created": 12, "resolved": 9, "critical": 2}]}
```
`series` counts cases **created** in the bucket by category and current status (only non-empty combinations); `totals` has one entry per bucket (zero filled): cases created, cases resolved (by `closed_at`), and created cases with priority URGENT or CRITICAL.

`GET /analytics/departments/{id}?days=30` and `GET /analytics/departments?days=30` (extended; **meaning change**: `resolved`, `median_resolution_hours`, `sla_compliance_pct` now cover cases closed in the last `days` days, matching the page labels "Resolved (30d)"; they used to cover all time)
```json
{"department_id": "road_maintenance", "name": "Road Maintenance", "days": 30, "incoming": 89, "active": 23, "resolved": 66, "median_resolution_hours": 31.0,
 "sla_compliance_pct": 82.0, "reopened": 4, "backlog_age_days": 8.0, "recurring_cases": 3,
 "by_severity": [{"severity": "CRITICAL", "count": 5}, {"severity": "HIGH", "count": 12}, {"severity": "MEDIUM", "count": 28}, {"severity": "LOW", "count": 21}]}
```
`by_severity` is the open workload by severity, always the four severities in that order (zeros included); `recurring_cases` is the number of recurring problem sites of the department. The list endpoint returns the same object per department in `items`.

`GET /analytics/wards?days=` (extended; `days` optional, default all time) item: `{"ward_id", "label", "name", "cases", "open", "sla_breached", "reopened", "critical", "backlog", "median_resolution_days", "recurrence", "by_category": [{"category", "count"}]}`
(`critical` = open cases with priority URGENT/CRITICAL, `backlog` = open cases, `recurrence` = recurring problem sites in the ward).

`GET /analytics/overview` (extended) adds `"priority_distribution": [{"priority": "URGENT", "count": 3}]` (open cases, all priorities present, zeros included).
