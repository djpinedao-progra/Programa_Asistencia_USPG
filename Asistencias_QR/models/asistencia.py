from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Asistencia:
    id: int | None
    carnet: str
    sesion_id: int
    fecha_hora: str

    def to_dict(self):
        return asdict(self)