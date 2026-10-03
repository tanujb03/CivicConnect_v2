"""The test run must not depend on a developer's ``.env`` (root conftest.py sets CIVIC_IGNORE_ENV_FILE before anything imports the backend)."""
import os

from backend.ai_gateway.envfile import load_env_file
from backend.core.config import Settings, settings


def test_the_root_conftest_disables_the_env_file():
    assert os.environ.get("CIVIC_IGNORE_ENV_FILE") == "1"
    assert Settings.model_config["env_file"] is None
    assert settings.AI_GATEWAY_STORE == os.environ["AI_GATEWAY_STORE"] == "demo"                  # the test run pins the demo store; never taken from a .env file


def test_the_ai_gateway_store_defaults_to_sql_and_demo_stays_selectable(monkeypatch):
    monkeypatch.delenv("AI_GATEWAY_STORE", raising=False)
    assert Settings().AI_GATEWAY_STORE == "sql"
    monkeypatch.setenv("AI_GATEWAY_STORE", "demo")
    assert Settings().AI_GATEWAY_STORE == "demo"


def test_the_default_env_file_search_is_off_but_explicit_paths_still_work(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("CIVIC_TEST_ONLY_KEY=abc\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    env: dict = {}
    assert load_env_file(environ=env) == [] and env == {}                                         # a .env in the cwd is ignored under the switch
    assert load_env_file([tmp_path / ".env"], env) == ["CIVIC_TEST_ONLY_KEY"] and env["CIVIC_TEST_ONLY_KEY"] == "abc"
