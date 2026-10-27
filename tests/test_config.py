import pytest

from app.config import load_config


def test_postgres_schema_configures_isolated_search_path(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:password@example.test/asistencia",
    )
    monkeypatch.setenv("DB_SCHEMA", "classroom_pruebas")

    config = load_config({"APP_ENV": "testing", "SECRET_KEY": "test"})

    assert config["DB_SCHEMA"] == "classroom_pruebas"
    assert config["SQLALCHEMY_ENGINE_OPTIONS"] == {
        "connect_args": {"options": "-csearch_path=classroom_pruebas"}
    }


@pytest.mark.parametrize("schema", ["public;drop schema public", "Con Espacios", "123"])
def test_postgres_schema_rejects_unsafe_names(monkeypatch, schema):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:password@example.test/asistencia",
    )
    monkeypatch.setenv("DB_SCHEMA", schema)

    with pytest.raises(RuntimeError, match="DB_SCHEMA"):
        load_config({"APP_ENV": "testing", "SECRET_KEY": "test"})
