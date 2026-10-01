"""List/download figshare files for large image datasets (RDD2022) to an EXTERNAL directory.

``show_license`` prints what figshare's own API reports for the article's licence: use it to resolve the
RDD2022 CC BY vs CC BY-SA question at the primary source before downloading. Large files require an
explicit size allowance; md5 is verified when figshare provides it.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

from ..errors import DataSourceError

API = "https://api.figshare.com/v2/articles/{id}"


class FigshareClient:
    def __init__(self, article_id: int | str, *, client: httpx.Client | None = None, timeout: float = 60.0):
        self.article_id = str(article_id)
        self._client = client or httpx.Client(timeout=timeout, follow_redirects=True)

    def article(self) -> dict:
        r = self._client.get(API.format(id=self.article_id))
        if r.status_code >= 400:
            raise DataSourceError(f"figshare API returned HTTP {r.status_code}")
        return r.json()

    def show_license(self) -> dict:
        a = self.article()
        return {"title": a.get("title"), "doi": a.get("doi"), "license": a.get("license"), "version": a.get("version"),
                "published_date": a.get("published_date")}

    def list_files(self) -> list[dict]:
        return [{"id": f.get("id"), "name": f.get("name"), "size": f.get("size"), "md5": f.get("computed_md5") or f.get("md5"),
                 "download_url": f.get("download_url")} for f in self.article().get("files", [])]

    def download(self, file: dict, out_dir: Path, *, allow_gb: float = 2.0) -> Path:
        size = file.get("size") or 0
        if size > allow_gb * 1024 ** 3:
            raise DataSourceError(f"{file['name']} is {size / 1024 ** 3:.1f} GB (> allowance {allow_gb} GB). Pass a larger --allow-gb deliberately.")
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / Path(file["name"]).name
        md5 = hashlib.md5()
        with self._client.stream("GET", file["download_url"]) as r:
            if r.status_code >= 400:
                raise DataSourceError(f"download failed: HTTP {r.status_code}")
            with dest.open("wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)
                    md5.update(chunk)
        if file.get("md5") and md5.hexdigest() != file["md5"]:
            raise DataSourceError(f"md5 mismatch for {dest.name}: expected {file['md5']}, got {md5.hexdigest()}")
        return dest
