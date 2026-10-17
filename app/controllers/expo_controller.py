"""Public Expo registration and administrator-only attendance reports."""
import io

from flask import render_template, request, redirect, url_for, flash, send_file, current_app, abort
from flask_login import current_user

from app.controllers import expo
from app.controllers.decorators import roles_required
from app.services.expo_service import ExpoService
from app.time_utils import local_datetime
from app.views.reports.excel_builder import build_expo_workbook
from app.views.reports.pdf_builder import build_expo_report_pdf
from app.views.reports.qr_builder import build_qr_png

CATEGORIES = {'estudiante': 'Estudiante', 'catedratico': 'Catedrático', 'publico': 'Público general'}


@expo.route('/expo-san-pablo', methods=['GET', 'POST'])
def registration():
    service = ExpoService()
    access_enabled = service.is_registration_enabled()
    values = request.form if request.method == 'POST' else {}
    if request.method == 'POST':
        if not access_enabled:
            flash('El registro de Expo San Pablo está deshabilitado.', 'error')
            return render_template(
                'expo/expo_registration.html', categories=CATEGORIES, values=values,
                registered=False, access_enabled=False,
            ), 403
        try:
            registered = service.register(
                request.form.get('name', ''),
                request.form.get('email', ''),
                request.form.get('category', ''),
                request.form.get('participation', ''),
                request.form.get('opinion', ''),
                request.form.get('consent', ''),
            )
            if not registered:
                flash('Este correo ya tiene asistencia registrada. No se sumó un registro nuevo.', 'warning')
                return redirect(url_for('expo.registration'))
            flash('¡Gracias! Tu asistencia y participación quedaron registradas.', 'success')
            return redirect(url_for('expo.registration', registrado='1'))
        except ValueError as error:
            flash(str(error), 'error')
    return render_template('expo/expo_registration.html', categories=CATEGORIES, values=values,
                           registered=request.args.get('registrado') == '1',
                           access_enabled=access_enabled)


def public_url():
    path = url_for('expo.registration')
    base = current_app.config.get('APP_BASE_URL', '')
    return base + path if base else url_for('expo.registration', _external=True)


def report_data():
    category = request.args.get('categoria', '')
    if category and category not in CATEGORIES:
        abort(400, description='Categoría inválida.')
    return category, ExpoService().count_by_category()


@expo.get('/admin/expo-san-pablo')
@roles_required('admin')
def report():
    service = ExpoService()
    category, counts = report_data()
    page = service.paginate(category, per_page=25)
    return render_template('expo/expo_report.html', categories=CATEGORIES, category=category,
                           counts=counts, total=sum(counts.values()), page=page,
                           public_url=public_url(),
                           access_enabled=service.is_registration_enabled())


@expo.post('/admin/expo-san-pablo/acceso')
@roles_required('admin')
def update_access():
    enabled = request.form.get('enabled') == '1'
    ExpoService().set_registration_enabled(enabled, actor_id=current_user.id)
    flash(
        'Registro público de Expo San Pablo habilitado.' if enabled
        else 'Registro público de Expo San Pablo deshabilitado.',
        'success',
    )
    return redirect(url_for('expo.report'))


@expo.get('/admin/expo-san-pablo/qr.png')
@roles_required('admin')
def qr():
    output = io.BytesIO(build_qr_png(public_url()))
    return send_file(output, mimetype='image/png', as_attachment=request.args.get('descargar') == '1',
                     download_name='QR-Expo-San-Pablo.png')


def date_label(row):
    return local_datetime(row.recorded_at, current_app.config['APP_TIMEZONE']).strftime('%d/%m/%Y %H:%M')


@expo.get('/admin/expo-san-pablo/reporte.xlsx')
@roles_required('admin')
def excel_report():
    category, counts = report_data()
    attendees = [
        {
            'name': row.name,
            'email': row.email,
            'category': row.category,
            'participation': row.participation,
            'opinion': row.opinion,
            'recorded_at': date_label(row),
        }
        for row in ExpoService().list_filtered(category)
    ]
    output = io.BytesIO(build_expo_workbook(category, CATEGORIES, counts, attendees))
    return send_file(output, as_attachment=True, download_name='Asistencia-Expo-San-Pablo.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@expo.get('/admin/expo-san-pablo/reporte.pdf')
@roles_required('admin')
def pdf_report():
    category, counts = report_data()
    attendees = [
        {
            'name': row.name,
            'email': row.email,
            'category': row.category,
            'participation': row.participation,
            'opinion': row.opinion,
            'recorded_at': date_label(row),
        }
        for row in ExpoService().list_filtered(category)
    ]
    output = io.BytesIO(
        build_expo_report_pdf(category, CATEGORIES, counts, attendees)
    )
    return send_file(output, as_attachment=True, download_name='Asistencia-Expo-San-Pablo.pdf', mimetype='application/pdf')
