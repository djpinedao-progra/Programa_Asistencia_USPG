"""Temporary replacement passwords: stored hashed, expire, and activate only upon login."""
import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models import PasswordReplacement
from app.repositories import UserRepository
from app.services import AuditService, UserService

REPLACEMENT_MINUTES = 15
REQUEST_COOLDOWN_MINUTES = 2


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def send_password(email, password):
    host = os.getenv("SMTP_HOST", "")
    sender = os.getenv("SMTP_FROM", "")
    if not host or not sender:
        raise RuntimeError("Configura SMTP_HOST y SMTP_FROM para recuperar contraseñas.")
    message = EmailMessage()
    message["Subject"] = "USPG — Contraseña temporal de reemplazo"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        f"Tu contraseña temporal es: {password}\n\n"
        f"Es válida por {REPLACEMENT_MINUTES} minutos y solo puede activarse una vez. "
        "Al utilizarla se reemplaza tu contraseña anterior. "
        "Cámbiala desde Seguridad después de iniciar sesión. "
        "Si no solicitaste la recuperación, ignora este mensaje; tu contraseña actual sigue vigente."
    )
    use_ssl = os.getenv("SMTP_SSL", "false").lower() == "true"
    port = int(os.getenv("SMTP_PORT", "465" if use_ssl else "587"))
    context = ssl.create_default_context()
    server = (
        smtplib.SMTP_SSL(host, port, timeout=15, context=context)
        if use_ssl
        else smtplib.SMTP(host, port, timeout=15)
    )
    with server:
        if not use_ssl:
            server.starttls(context=context)
        username = os.getenv("SMTP_USERNAME", "")
        if username:
            server.login(username, os.getenv("SMTP_PASSWORD", ""))
        server.send_message(message)


def request_replacement(email):
    user = UserRepository().find_by_email(email)
    if not user or UserService.email_role(user.email) != user.role:
        return
    now = datetime.now(timezone.utc)
    pending = db.session.get(PasswordReplacement, user.id)
    # Per-account throttle so repeated requests cannot flood the mailbox.
    if pending and now < _utc(pending.requested_at) + timedelta(minutes=REQUEST_COOLDOWN_MINUTES):
        return
    password = secrets.token_urlsafe(18)
    if not pending:
        pending = PasswordReplacement(user_id=user.id)
        db.session.add(pending)
    pending.password_hash = generate_password_hash(password)
    pending.requested_at = now
    pending.expires_at = now + timedelta(minutes=REPLACEMENT_MINUTES)
    try:
        db.session.flush()
        send_password(user.email, password)
        AuditService.record(user.id, "password_replacement_requested", "user", user.id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Never log the address, the temporary password, or SMTP credentials.
        current_app.logger.error("No se pudo enviar el correo de recuperación.")


def authenticate(user, password):
    pending = db.session.get(PasswordReplacement, user.id)
    if user.check_password(password):
        if pending:
            db.session.delete(pending)
            db.session.commit()
        return True
    if (
        pending
        and _utc(pending.expires_at) > datetime.now(timezone.utc)
        and check_password_hash(pending.password_hash, password)
    ):
        user.password_hash = pending.password_hash
        db.session.delete(pending)
        AuditService.record(user.id, "password_replacement_activated", "user", user.id)
        db.session.commit()
        return True
    return False
