from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Curso:
    id: int | None
    codigo: str
    nombre: str
    seccion: str = ""
    docente: str = ""
    estado: str = "activo"

    def to_dict(self):
        return asdict(self)
