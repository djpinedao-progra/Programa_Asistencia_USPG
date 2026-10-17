# Servicios

- Implementan validaciones, reglas y cálculos de cada dominio.
- Reciben valores y objetos, y devuelven datos o errores de dominio.
- No deben importar `request`, `render_template`, `flash` ni `redirect`.
- Las consultas y persistencia deben delegarse a repositorios.
- Los generadores de PDF, Excel, CSV y QR pertenecen a `app/views/reports/`.
- `seed_service.py` prepara los datos demo usados por `iniciar.py`.
- `course_enrollment_service.py` concentra las reglas de matrícula de alumnos.
- Revisa `docs/PENDIENTES.md` para las dependencias heredadas aún por extraer.
