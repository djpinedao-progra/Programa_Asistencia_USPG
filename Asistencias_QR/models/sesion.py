from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Sesion:
    id: int | None
    curso: str
    fecha_hora: str
    token_qr: str
    qr_file: str | None = None

    def to_dict(self):
        return asdict(self)