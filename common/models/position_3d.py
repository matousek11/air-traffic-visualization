from dataclasses import dataclass


@dataclass
class Position3D:
    lat: float
    lon: float
    flight_level: float
