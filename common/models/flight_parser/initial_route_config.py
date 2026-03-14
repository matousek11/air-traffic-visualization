from dataclasses import dataclass

@dataclass
class InitialRouteConfig:
    """Represents initial settings of flight route: N0450F310"""
    raw: str
    true_air_speed: int
    flight_level: int