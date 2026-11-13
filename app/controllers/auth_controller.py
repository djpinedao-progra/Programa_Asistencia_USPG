import hmac

from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from app.controllers import main
from app.services import ExpoService, UserService
from app.services.google_login_service import (
    GoogleLoginConfigurationError,
    GoogleLoginService,
)


def _google_login_error(message):
    """Regresa a la pantalla local y conserva el mensaje de Google."""
    flash(message, "error")
    return redirect(url_for("main.login", acceso="local", error_google=message))


@main.route("/", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    # Google puede ser la entrada principal. "acceso=local" mantiene una
    # alternativa con contraseña para no impedir el acceso durante una incidencia.
    if (
        request.method == "GET"
        and GoogleLoginService.auto_redirect_enabled()
        and request.args.get("acceso") != "local"
    ):
        return redirect(url_for("main.google_login", next=request.args.get("next", "")))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = UserService().find_by_login_identifier(identifier)
        from app.recovery import authenticate
        if user and UserService.role_is_allowed_for_email(
            user.email, user.role
        ) and authenticate(user, password):
            login_user(user)
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("main.dashboard"))
        flash("Correo o contraseña incorrectos.", "error")
    return render_template(
        "auth/login.html",
        expo_access_enabled=ExpoService().is_registration_enabled(),
        google_login_enabled=GoogleLoginService.enabled(),
        google_login_error=request.args.get("error_google", "").strip(),
    )


@main.get("/auth/google")
def google_login():
    """Envía a Google para identificar a la persona sin guardar contraseñas."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    try:
        authorization_url, state, code_verifier = GoogleLoginService().authorization_url()
    except GoogleLoginConfigurationError as error:
        return _google_login_error(str(error))
    session["google_login_state"] = state
    session["google_login_code_verifier"] = code_verifier
    next_url = request.args.get("next", "")
    session["google_login_next"] = (
        next_url if next_url.startswith("/") and not next_url.startswith("//") else ""
    )
    return redirect(authorization_url)


@main.get("/auth/google/callback")
def google_login_callback():
    """Comprueba la respuesta de Google y abre una cuenta ya registrada."""
    expected_state = session.pop("google_login_state", "")
    code_verifier = session.pop("google_login_code_verifier", "")
    received_state = request.args.get("state", "")
    if not hmac.compare_digest(expected_state, received_state):
        abort(400)
    if request.args.get("error"):
        flash("Google canceló el inicio de sesión.", "warning")
        return _google_login_error("Google canceló el inicio de sesión.")
    try:
        email = GoogleLoginService().verified_email_from_code(
            request.url, received_state, code_verifier
        )
    except (GoogleLoginConfigurationError, ValueError) as error:
        current_app.logger.warning("Inicio con Google rechazado: %s", error)
        return _google_login_error(str(error))
    user = UserService().find_by_login_identifier(email)
    if not user or not UserService.role_is_allowed_for_email(user.email, user.role):
        current_app.logger.warning(
            "Inicio con Google rechazado para una cuenta no registrada: %s", email
        )
        flash("Tu cuenta de Google no está registrada para usar este sistema.", "error")
        return _google_login_error(
            "Tu cuenta de Google no está registrada para usar este sistema."
        )
    login_user(user)
    next_url = session.pop("google_login_next", "")
    return redirect(next_url or url_for("main.dashboard"))


@main.route("/registro", methods=["GET", "POST"])
def student_registration():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        try:
            UserService().register_student(
                request.form.get("name", ""),
                request.form.get("email", ""),
                request.form.get("carnet", ""),
                request.form.get("password", ""),
            )
            flash("Cuenta de estudiante creada. Inicia sesión para continuar.", "success")
            return redirect(url_for("main.login"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template("auth/register.html")


@main.post("/salir")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("main.login"))


@main.get("/panel")
@login_required
def dashboard():
    if current_user.role == "admin":
        return redirect(url_for("main.admin_dashboard"))
    if current_user.role == "docente":
        return redirect(url_for("main.teacher_dashboard"))
    return redirect(url_for("main.student_dashboard"))


@main.route("/cuenta/seguridad", methods=["GET", "POST"])
@login_required
def account_security():
    if request.method == "POST":
        try:
            UserService().change_password(
                current_user.id,
                request.form.get("current_password", ""),
                request.form.get("new_password", ""),
                request.form.get("confirm_password", ""),
            )
            flash("Contraseña actualizada.", "success")
            return redirect(url_for("main.account_security"))
        except ValueError as error:
            flash(str(error), "error")
    return render_template("auth/account_security.html")


@main.route("/recuperar-contrasena", methods=["GET", "POST"])
def recover_password():
    if request.method == "POST":
        from app.recovery import request_replacement
        email = request.form.get("email", "").strip().lower()
        if not UserService.email_role(email):
            flash("Ingresa un correo universitario de alumno, catedrático o administrador.", "error")
        else:
            request_replacement(email)
            flash("Si el correo pertenece a una cuenta válida, recibirás una contraseña temporal. Revisa también correo no deseado.", "success")
            return redirect(url_for("main.login"))
    return render_template("auth/recover_password.html")
