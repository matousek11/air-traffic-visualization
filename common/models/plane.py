"""
House plane object from NM B2B
"""
import string
from collections import deque

from common.helpers.physics_calculator import PhysicsCalculator
from common.models.position import Position

class Plane:
    """
    Represents plane object from NM B2B
    """
    def __init__(self, aircraft_type: string):
        self.aircraft_type = aircraft_type
        self.positions = deque(maxlen=3)
        self.heading = None
        self.speed = None
        self.vertical_speed = None

    def add_position(self, position: Position) -> None:
        """
        Appends newest Position object as last known position of Plane
        """
        self.positions.append(position)
        if len(self.positions) < 2:
            return

        self.calculate_attributes_from_positions()

    def calculate_attributes_from_positions(self) -> None:
        """
        Calculate plane quantities like vertical speed from last two positions
        """
        PhysicsCalculator.get_horizontal_speed(
            self.positions[-1], self.positions[-2]
        )
