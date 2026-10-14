# Pendientes de la migración MVC

## Diferencias y comportamiento preservado

- El mensaje del QR anuncia vencimiento en 5 minutos, pero `app/config.py`
  define `QR_SESSION_MINUTES = 1` y `AttendanceService` limita la duración a
  1 minuto. No se cambió; ajustar textos o duración requiere una decisión de
  producto.
- El README ya mostraba los dominios institucionales que `iniciar.py` crea.
  Los dominios `@demo.uspg` citados en el análisis inicial no aparecían en esta
  revisión; la guía ahora confirma las cuentas verificadas en `seed_service.py`.
- Se unificó la documentación de Expo: está integrada en este proyecto
  independiente y `migrate-expo` prepara su tabla en la instalación actual.

## Trabajo estructural que aún falta

- Aún hay SQL o persistencia en controladores, por lo que la regla
  `controllers → services → repositories → models` no está cumplida en todos
  los módulos: `controllers/admin_controller.py:122-289`,
  `controllers/teacher_controller.py:15-184`,
  `controllers/teacher_attendance_controller.py:9-282`,
  `controllers/admin_reports_controller.py:57-72`,
  `controllers/expo_controller.py:54-115` y
  `controllers/export_controller.py:11,43`. Migrar cada lectura/escritura a su
  repositorio/servicio y ejecutar `rg "db\\.session|select\\(" app/controllers app/views`.
- Servicios que todavía acceden directamente a `db.session` o construyen
  consultas SQLAlchemy: `course_service.py`, `course_enrollment_service.py`,
  `admin_metrics_service.py`, `student_metrics_service.py`,
  `teacher_metrics_service.py`, `recovery_service.py`, `user_service.py` y
  `audit_service.py`. El acceso de datos debe quedar detrás de repositorios.
- Los controladores todavía importan símbolos en bloque desde
  `controllers/_support.py`; reemplazar los imports con dependencias explícitas
  después de extraer sus consultas y helpers.
- Falta completar docstrings breves en español para todas las clases y
  funciones públicas de servicios, repositorios y controladores.
- Ningún archivo Python de `app/` supera actualmente las 300 líneas. Los
  controladores `admin_controller.py` y `teacher_attendance_controller.py`
  siguen cerca del límite (296 y 285 líneas) y contienen rutas extensas;
  reducirlos con las extracciones anteriores.
- Rutas/funciones aún mayores de 25 líneas: `controllers/admin_controller.py`
  (`admin_dashboard`, línea 9), `controllers/admin_courses_controller.py`
  (`admin_import_course_enrollments`, línea 9),
  `controllers/admin_reports_controller.py` (`admin_session_report_pdf`, línea
  56), `controllers/export_controller.py` (`export_attendance`, línea 10;
  `export_attendance_pdf`, línea 42),
  `controllers/teacher_attendance_controller.py` (`_start_attendance_session`,
  línea 47; `teacher_session`, línea 126; `attendance_session_status`, línea
  175; `set_session_attendance`, línea 210; `close_attendance_session`, línea
  256) y `controllers/teacher_controller.py` (`teacher_history`, línea 80;
  `send_teacher_notice`, línea 161). Pasar la lógica de dominio a servicios.
- Los endpoints y reglas registrados coinciden con los 48 elementos de
  `endpoints_antes.txt`, pero el orden de registro cambió al agrupar rutas en
  módulos. La igualdad por conjuntos está verificada; la comparación textual
  línea por línea todavía difiere en orden.
- La revisión visual en navegador se ejecutó contra una base SQLite en memoria:
  cargaron las pantallas de menú admin/docente/alumno y seguridad; el docente
  inició y cerró una sesión QR; el registro público Expo y los reportes PDF,
  Excel, QR y CSV respondieron correctamente. La marcación del alumno con QR
  también está cubierta por `tests/test_attendance_flow.py`.
- No se ejecutó `python iniciar.py --demo` sobre el archivo persistente de
  `instance/`, para no modificar datos locales existentes; el servicio de
  semilla sí tiene una prueba idempotente en base SQLite temporal.
