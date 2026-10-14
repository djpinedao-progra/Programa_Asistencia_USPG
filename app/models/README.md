# Modelos

- Cada módulo define tablas SQLAlchemy por entidad.
- Aquí viven columnas, índices, constraints, relaciones y métodos del registro.
- `__init__.py` reexporta las clases para conservar imports públicos.
- No se deben agregar rutas, respuestas Flask ni reglas de varios dominios.
- Mantén los nombres de tabla y columnas compatibles con las bases existentes.
- Para cambios de esquema existente, agrega la migración correspondiente en `app/cli.py`.
