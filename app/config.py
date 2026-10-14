import os
import secrets


def load_config(test_config=None):
    app_env = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
    env_secret = os.getenv("SECRET_KEY")
    database_url = os.getenv("DATABASE_URL", "sqlite:///luis_independiente.db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace(
            "postgres://", "postgresql+psycopg://", 1
        )
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )

    config = {
        "SECRET_KEY": env_secret or secrets.token_urlsafe(48),
        "SQLALCHEMY_DATABASE_URI": database_url,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": app_env == "production",
        "QR_SESSION_MINUTES": 1,
        "APP_BASE_URL": os.getenv(
            "APP_BASE_URL", os.getenv("RENDER_EXTERNAL_URL", "")
        ).rstrip("/"),
        "APP_TIMEZONE": os.getenv("APP_TIMEZONE", "America/Guatemala"),
        "APP_ENV": app_env,
    }
    if test_config:
        config.update(test_config)
    if config.get("APP_ENV") == "production":
        config["SESSION_COOKIE_SECURE"] = True
    if (
        config.get("APP_ENV") == "production"
        and not env_secret
        and not (test_config and test_config.get("SECRET_KEY"))
    ):
        raise RuntimeError("SECRET_KEY es obligatoria cuando APP_ENV=production.")
    if (
        config.get("APP_ENV") == "production"
        and not os.getenv("DATABASE_URL")
        and not test_config
    ):
        raise RuntimeError("DATABASE_URL es obligatoria en producción.")
    return config
