---
name: wp-report
description: Template for the end-of-work-package report (max 25 lines, plan rule 13) and the instruction to update the section 9 status table of docs/BACKEND_BUILD_PLAN.md. Use at the end of every work package.
---

# Work-package report

After the commit, check authorship: `git log -1 --format='%an <%ae>%n%B'` must show Tanuj Vivek Bhide and no trailer.

Then update the one-line row of the work package in the **section 9 status table** of `docs/BACKEND_BUILD_PLAN.md` (state, commit hash, short notes, and the outcome of any mandatory `backend-reviewer` pass). States: `TODO`, `IN PROGRESS`, `DONE (tests green)`, `BLOCKED (reason)`.

Report, at most 25 lines, in this order:

```
WP<n> <title>: <state>   commit <hash>
Files changed: <list, grouped>
Commands: pytest ai backend -q -> N passed, S skipped, F failed | ruff <files> -> clean/<n new> | alembic heads -> <head> | alembic check -> <result> | PG/Redis tests -> <counts>
Review: backend-reviewer <blocker/major/minor counts and what was done about each> (or "not required")
Contract changes: <additive fields / change-log entry / none>
Failures: <plain statement or none>
Not verified: <list>
Needs Tanuj: <questions or none>
```

Honest reporting: failing tests, skipped steps and unverified claims are stated as they are. Synthetic data gives no real-world accuracy claim.
