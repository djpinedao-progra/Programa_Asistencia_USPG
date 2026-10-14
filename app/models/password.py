from app.extensions import db


class PasswordReplacement(db.Model):
    __tablename__ = "password_replacements"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    password_hash = db.Column(db.String(255), nullable=False)
    requested_at = db.Column(db.DateTime(timezone=True), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
