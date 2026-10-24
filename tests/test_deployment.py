import pytest
from sqlalchemy import func, select

from app import db
from app.models import User
from prepare_production import prepare_database


def test_prepare_database_creates_admin_once(app, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "deploy@administrador.uspg.edu.gt")
    monkeypatch.setenv("ADMIN_PASSWORD", "Render-USPG-2026!")

    assert prepare_database(app) is True
    assert prepare_database(app) is False

    with app.app_context():
        assert db.session.scalar(
            select(func.count()).select_from(User).where(User.role == "admin")
        ) == 1
        admin = db.session.scalar(
            select(User).where(User.role == "admin")
        )
        assert admin.email == "deploy@administrador.uspg.edu.gt"
        assert admin.check_password("Render-USPG-2026!")


def test_prepare_database_requires_initial_credentials(app, monkeypatch):
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="ADMIN_EMAIL y ADMIN_PASSWORD"):
        prepare_database(app)


def test_prepare_database_can_reset_existing_admin_credentials(app, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "deploy@administrador.uspg.edu.gt")
    monkeypatch.setenv("ADMIN_PASSWORD", "Render-USPG-2026!")
    assert prepare_database(app) is True

    monkeypatch.setenv("ADMIN_EMAIL", "nuevo@administrador.uspg.edu.gt")
    monkeypatch.setenv("ADMIN_PASSWORD", "Nueva-Clave-2026!")
    monkeypatch.setenv("RESET_ADMIN_CREDENTIALS", "true")

    assert prepare_database(app) is True

    with app.app_context():
        admin = db.session.scalar(db.select(User).where(User.role == "admin"))
        assert admin.email == "nuevo@administrador.uspg.edu.gt"
        assert admin.check_password("Nueva-Clave-2026!")


def test_prepare_database_can_reset_demo_once(app, sample_data, monkeypatch):
    monkeypatch.setenv("RESET_DEMO_DATA", "true")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@administrador.uspg.edu.gt")

    assert prepare_database(app) is True

    with app.app_context():
        users = list(db.session.scalars(db.select(User)))
        assert len(users) == 1
        assert users[0].email == "admin@administrador.uspg.edu.gt"
        for table in db.metadata.sorted_tables:
            if table.name != User.__tablename__:
                assert db.session.scalar(
                    db.select(db.func.count()).select_from(table)
                ) == 0
