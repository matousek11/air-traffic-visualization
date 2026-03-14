from dataclasses import dataclass

@dataclass
class RawRouteSegment:
    ident: str  # (BALTU) or coordinates
    via_airway: str | None  # (Z93, DCT)
    true_air_speed: int | None = None
    flight_level: int | None = None

    def __repr__(self):
        extras = ""
        if self.true_air_speed: extras += f" [{self.true_air_speed}/{self.flight_level}]"
        return f"({self.ident} --{self.via_airway}-->{extras})"