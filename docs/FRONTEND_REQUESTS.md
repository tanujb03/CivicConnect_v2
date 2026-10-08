# Frontend requests to the backend

The **frontend session appends** an entry here whenever an app needs something the backend does not serve yet (endpoint missing, field missing, shape mismatch, error code needed, demo data, CORS origin, ...).
The **backend session reads this file at the start of every wave and after every work package** (plan WP10), answers each entry with `DONE <commit>`, `WON'T <reason>` or `QUESTION`, and does the work.
Contract changes the backend makes are recorded in `docs/V1_CHANGE_LOG.md`; the page-by-page reference of what is already served is `docs/FRONTEND_API_NEEDS.md`.

Rules: one entry per need; keep old entries (do not delete answered ones); contract changes are additive (a removed or renamed field needs a change-log entry and an entry here).

## Entry template

```
### YYYY-MM-DD · <app> · <page or screen> · <REQUEST | NOTE | QUESTION>
**Needed:** what is missing or wrong, in one or two sentences.
**Example request:** `GET /api/v1/...` (or the call the app makes today)
**Example response (wanted):** a small JSON sample of the shape the page needs
**Seen instead:** what the backend returns today (status, body, error code), if known
**Answer (backend):** DONE <commit> | WON'T <reason> | QUESTION <what we need to know>
```

## Entries

(none yet)
