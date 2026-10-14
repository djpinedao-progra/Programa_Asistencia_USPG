# Repositorios

- Cada repositorio concentra lecturas y escrituras de una entidad o relación.
- Los métodos reciben parámetros explícitos y devuelven modelos o datos simples.
- Las expresiones SQLAlchemy y el acceso a `db.session` pertenecen a esta capa.
- Los servicios usan repositorios para evitar consultas dispersas.
- No se deben aplicar reglas de negocio ni importar objetos de petición HTTP.
- Hay servicios heredados con consultas directas pendientes de migración.
