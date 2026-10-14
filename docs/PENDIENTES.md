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

- Se retiró el acceso directo a `db.session` y `select(...)` de
  `app/controllers/`, `app/services/` y `app/views/`; las consultas y
  persistencia de los servicios se movieron a repositorios, incluidos los
  cálculos agregados de asistencia y las operaciones de respaldo. Las búsquedas
  de `db.session`/`select(` en esos tres niveles no devuelven resultados.
- Los controladores ya no importan ni llaman repositorios directamente, y se
  eliminaron los imports wildcard de `controllers/_support.py`. La revisión
  estática confirma la dirección de dependencias prevista para consultas y
  persistencia.
- Falta completar docstrings breves en español para todas las clases y
  funciones públicas de servicios, repositorios y controladores.
- Ningún archivo Python de `app/` supera actualmente las 300 líneas. Los 47
  handlers registrados en los controladores tienen como máximo 24 líneas.
- Los endpoints, reglas y métodos registrados coinciden exactamente con los
  48 elementos de `endpoints_antes.txt` al compararlos como conjunto; el orden
  de registro cambia al agrupar rutas en módulos, por lo que la comparación
  textual línea por línea difiere.
- La revisión visual en navegador se ejecutó contra una base SQLite en memoria:
  cargaron las pantallas de menú admin/docente/alumno y seguridad; el docente
  inició y cerró una sesión QR; el registro público Expo y los reportes PDF,
  Excel, QR y CSV respondieron correctamente. La marcación del alumno con QR
  también está cubierta por `tests/test_attendance_flow.py`.
- No se ejecutó `python iniciar.py --demo` sobre el archivo persistente de
  `instance/`, para no modificar datos locales existentes; el servicio de
  semilla sí tiene una prueba idempotente en base SQLite temporal.
