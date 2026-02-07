from dataclasses import dataclass


@dataclass
class DepartureProcedure:
    """Represents departure procedure from airport and is set in flight route"""
    ident: str