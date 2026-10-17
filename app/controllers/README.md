# Controladores

- Contienen rutas Flask y adaptan HTTP a llamadas de servicios.
- Aquí se leen formularios, parámetros y el usuario autenticado.
- Aquí se decide entre `render_template`, `redirect`, `flash` y respuestas de archivo.
- `decorators.py` conserva la autorización por rol.
- `__init__.py` define y registra los blueprints públicos `main` y `expo`.
- No se deben implementar reglas de negocio ni generar archivos de reporte aquí.
- Las consultas SQL que todavía existen están identificadas en `docs/PENDIENTES.md`.
