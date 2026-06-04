import tomllib
from pathlib import Path


def test_default_database_url_uses_persistent_data_directory():
    config = tomllib.loads(Path("config/settings.toml").read_text(encoding="utf-8"))

    assert config["database"]["url"] == "sqlite+aiosqlite:///./data/github_sentinel.db"


def test_env_example_matches_persistent_database_path():
    env_example = Path("env.example").read_text(encoding="utf-8")

    assert "DATABASE_URL=sqlite+aiosqlite:///./data/github_sentinel.db" in env_example
    assert "DATABASE_URL=sqlite+aiosqlite:///./github_sentinel.db" not in env_example
