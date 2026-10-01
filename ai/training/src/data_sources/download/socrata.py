"""Download a bounded slice of a Socrata (SODA) dataset to an EXTERNAL directory.

Never run inside the repository tree (the CLI enforces the output-path guard). Pulls are capped, ordered
for stable paging, and recorded in ``RETRIEVAL.json`` (endpoint, parameters without credentials, timestamp,
row count, sha256, card fingerprint) so the exact extract is reproducible/auditable.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ..card_schema import SourceCard
from ..errors import DataSourceError

HARD_MAX_ROWS = 2_000_000
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class SocrataDownloader:
    def __init__(self, card: SourceCard, *, client: httpx.Client | None = None, app_token: str | None = None,
                 sleep=time.sleep, timeout: float = 60.0):
        endpoint = card.data_access.get("endpoint", "")
        if not endpoint.startswith("https://") or "/resource/" not in endpoint:
            raise DataSourceError(f"card {card.id} has no Socrata endpoint")
        self.card, self.endpoint, self.app_token = card, endpoint, app_token
        self._client = client or httpx.Client(timeout=timeout)
        self._sleep = sleep
        self.host = urlparse(endpoint).hostname

    def where_clause(self, since: str | None, until: str | None, extra: str | None, date_field: str = "created_date") -> str | None:
        parts = []
        for val, op in ((since, ">="), (until, "<=")):
            if val:
                if not _DATE.match(val):
                    raise DataSourceError(f"date must be YYYY-MM-DD, got {val!r}")
                parts.append(f"{date_field} {op} '{val}T{'00:00:00' if op == '>=' else '23:59:59'}'")
        if extra:
            parts.append(f"({extra})")
        return " AND ".join(parts) or None

    def _get(self, params: dict) -> list[dict]:
        headers = {"X-App-Token": self.app_token} if self.app_token else {}
        for attempt in range(4):
            try:
                r = self._client.get(self.endpoint, params=params, headers=headers)
            except httpx.HTTPError as e:
                if attempt == 3:
                    raise DataSourceError(f"transport error: {type(e).__name__}") from e
                self._sleep(2 ** attempt)
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                self._sleep(2 ** attempt)
                continue
            if r.status_code >= 400:
                raise DataSourceError(f"HTTP {r.status_code} from {self.host}")
            data = r.json()
            if not isinstance(data, list):
                raise DataSourceError("unexpected response shape (expected a JSON array)")
            return data
        raise DataSourceError("unreachable")

    def download(self, out_dir: Path, *, since: str | None = None, until: str | None = None, where: str | None = None,
                 select: str | None = None, max_rows: int = 50_000, page_size: int = 5_000, date_field: str = "created_date") -> Path:
        if max_rows > HARD_MAX_ROWS:
            raise DataSourceError(f"max_rows exceeds the hard cap of {HARD_MAX_ROWS}")
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        base = {"$order": ":id"}
        w = self.where_clause(since, until, where, date_field)
        if w:
            base["$where"] = w
        if select:
            base["$select"] = select
        raw = out_dir / "raw.jsonl"
        total, offset = 0, 0
        with raw.open("w", encoding="utf-8", newline="\n") as fh:
            while total < max_rows:
                want = min(page_size, max_rows - total)
                rows = self._get({**base, "$limit": want, "$offset": offset})
                for r in rows:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                total += len(rows)
                offset += len(rows)
                if len(rows) < want:      # last page
                    break
        sha = hashlib.sha256(raw.read_bytes()).hexdigest()
        (out_dir / "RETRIEVAL.json").write_text(json.dumps({
            "source_id": self.card.id, "endpoint": self.endpoint, "params": base, "max_rows": max_rows, "rows": total,
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sha256": sha,
            "app_token_used": bool(self.app_token), "card_fingerprint": self.card.fingerprint(),
            "license_verified": self.card.license_verified, "terms_acknowledged": True,
            "note": "External data: do not commit or redistribute (see source card)."}, indent=2) + "\n", encoding="utf-8")
        return raw
