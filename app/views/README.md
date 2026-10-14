# Vistas

- `templates/` contiene las plantillas Jinja agrupadas por rol y pantalla.
- `static/css/` conserva los estilos en módulos cargados en orden.
- `static/js/` contiene interacciones específicas de pantalla.
- `static/img/` guarda imágenes servidas mediante el endpoint Flask `static`.
- `reports/` contiene generadores sin acceso a Flask ni a la base de datos.
- Los generadores reciben datos listos y devuelven bytes.
- Las plantillas no deben ejecutar consultas ni cálculos de negocio pesados.
