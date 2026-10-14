"""Replacement passwords are hashed, expire, and activate only upon login."""
import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from werkzeug.security import check_password_hash, generate_password_hash
from app.models import PasswordReplacement, User
from app.repositories import UserRepository
from app.services import AuditService, UserService


def utc(value):
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
        "Es válida por 15 minutos y solo puede activarse una vez. "
        "Al utilizarla se reemplaza tu contraseña anterior. "
        "Cámbiala desde tu perfil después de iniciar sesión. "
        "Si no solicitaste la recuperación, ignora este mensaje; tu contraseña actual sigue vigente."
    )
    use_ssl = os.getenv("SMTP_SSL", "false").lower() == "true"
    port = int(os.getenv("SMTP_PORT", "465" if use_ssl else "587"))
    context = ssl.create_default_context()
    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=15, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=15)
    with server:
        if not use_ssl:
            server.starttls(context=context)
        username = os.getenv("SMTP_USERNAME", "")
        if username:
            server.login(username, os.getenv("SMTP_PASSWORD", ""))
        server.send_message(message)


def request_replacement(email, logger):
    users = UserRepository()
    user = users.find_by_exact_email(email)
    if not user or UserService.email_role(email) != user.role:
        return
    now = datetime.now(timezone.utc)
    pending = users.find_password_replacement(user.id)
    # Persistent per-account throttle; repeated requests cannot flood the mailbox.
    if pending and now < utc(pending.requested_at) + timedelta(minutes=2):
        return
    password = secrets.token_urlsafe(18)
    if not pending:
        pending = PasswordReplacement(user_id=user.id)
        users.stage_password_replacement(pending)
    pending.password_hash = generate_password_hash(password)
    pending.requested_at = now
    pending.expires_at = now + timedelta(minutes=15)
    try:
        users.flush()
        send_password(email, password)
        AuditService.record(user.id, "password_replacement_requested", "user", user.id)
        users.commit_changes()
    except Exception:
        users.rollback()
        # Do not log the email, temporary password, or SMTP credentials.
        logger.error("No se pudo enviar el correo de recuperación.")


def authenticate(user, password):
    users = UserRepository()
    pending = users.find_password_replacement(user.id)
    if user.check_password(password):
        if pending:
            users.delete_password_replacement(pending)
            users.commit_changes()
        return True
    if pending and utc(pending.expires_at) > datetime.now(timezone.utc) and check_password_hash(pending.password_hash, password):
        user.password_hash = pending.password_hash
        users.delete_password_replacement(pending)
        AuditService.record(user.id, "password_replacement_activated", "user", user.id)
        users.commit_changes()
        return True
    return False
