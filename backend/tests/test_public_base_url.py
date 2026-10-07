"""Signed LocalStorage URLs must be reachable from a phone (Expo app on the LAN or through a tunnel), so they are built from PUBLIC_BASE_URL, never from localhost."""
import pytest

from backend.core.config import Settings, settings
from backend.storage import LocalStorage
from backend.tests.helpers import JPEG, upload

PHONE_BASES = ["http://192.168.1.23:8000", "https://quiet-river-example.trycloudflare.com/"]


def test_public_base_url_defaults_to_localhost(monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    assert Settings().PUBLIC_BASE_URL == "http://localhost:8000"
    monkeypatch.setenv("PUBLIC_BASE_URL", PHONE_BASES[0])
    assert Settings().PUBLIC_BASE_URL == PHONE_BASES[0]


@pytest.mark.parametrize("base", PHONE_BASES)
def test_local_signed_urls_use_the_public_base_url(tmp_path, monkeypatch, base):
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", base)
    store = LocalStorage(tmp_path)
    prefix = f"{base.rstrip('/')}{settings.API_V1_STR}/evidence/blob/"
    up, down = store.upload_url("evidence/a.jpg", "image/jpeg", 60), store.download_url("evidence/a.jpg", 60)
    assert up.startswith(prefix) and down.startswith(prefix) and "localhost" not in up + down
    assert "//" not in up.split("//", 1)[1]                                                    # a trailing slash in the setting must not double up


@pytest.mark.parametrize("base", PHONE_BASES)
def test_upload_and_download_work_through_the_public_host(staffed, monkeypatch, base):
    """Init -> PUT -> complete -> signed GET, with the URLs handed to a phone and the requests arriving under the phone-facing host name."""
    e = staffed
    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", base)
    host = base.split("//", 1)[1].rstrip("/")
    ev = upload(e, "alice")                                                                    # the helper PUTs to the path of the returned upload_url
    meta = e.client.get(f"/api/v1/evidence/{ev['id']}", headers=e.headers("alice")).json()
    assert meta["download_url"].startswith(f"{base.rstrip('/')}/api/v1/evidence/blob/")
    got = e.client.get(meta["download_url"].removeprefix(base.rstrip("/")), headers={"Host": host})
    assert got.status_code == 200 and got.content == JPEG
