from flask import Flask

from app.extensions import db, login_manager


def create_app(test_config=None):
    app = Flask(
        __name__,
        template_folder="views/templates",
        static_folder="views/static",
    )
    from app.config import load_config

    app.config.from_mapping(load_config(test_config))
    db.init_app(app)
    login_manager.init_app(app)

    from app.utils.time_utils import local_datetime

    app.add_template_filter(
        lambda value: local_datetime(value, app.config["APP_TIMEZONE"]),
        "localtime",
    )

    from app import models
    from app.controllers import expo, main, register_controllers

    register_controllers()

    app.register_blueprint(main)
    app.register_blueprint(expo)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(models.User, int(user_id))

    from app.security import register_security_hooks

    register_security_hooks(app)
    from app.cli import register_commands

    register_commands(app)
    return app
