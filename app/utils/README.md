# Utilidades

- Aloja funciones transversales pequeñas que no pertenecen a un dominio.
- `time_utils.py` centraliza conversiones y límites de fechas.
- Las utilidades reciben sus dependencias como argumentos cuando sea posible.
- No deben importar controladores ni depender de una petición Flask.
- Reglas específicas de asistencia, cursos o usuarios pertenecen a servicios.
- Mantén aquí únicamente código reutilizable por más de una capa.
