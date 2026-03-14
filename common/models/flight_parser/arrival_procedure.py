from dataclasses import dataclass


@dataclass
class ArrivalProcedure:
    """Represents arrival procedure to airport and is set in flight route"""
    ident: str