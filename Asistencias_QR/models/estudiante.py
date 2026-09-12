from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Estudiante:
    carnet: str
    nombre: str
    correo: str
    carrera: str
    estado: str = "activo"

    def to_dict(self):
        return asdict(self)