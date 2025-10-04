"""
Used for test of physics calculator class
"""
import math

from common.helpers.physics_calculator import PhysicsCalculator
from common.models.position import Position


def test_distance_between_two_points() -> None:
    """
    Tests if distance between two points is correctly calculated
    """
    distance_in_km = PhysicsCalculator.get_distance_between_positions(0, 0, 5, 5)
    assert math.isclose(distance_in_km, 785, abs_tol=0.8)

def test_speed_between_two_positions() -> None:
    """
    Tests if speed in km/h between two points with given time is correctly calculated
    """
    speed_in_km = PhysicsCalculator.get_horizontal_speed(
        Position(0, 0, 0, 240),
        Position(5, 5, 5, 240)
    )

    assert math.isclose(speed_in_km, 157, abs_tol=0.2)

def test_vertical_speed() -> None:
    """
    Tests if vertical speed in m/s between two points with given time is correctly calculated
    """
    vertical_speed = PhysicsCalculator.get_vertical_speed(
        Position(0, 0, 0, 240),
        Position(30, 0, 0, 220)
    )

    assert math.isclose(vertical_speed, 1219, abs_tol=1)

    vertical_speed = PhysicsCalculator.get_vertical_speed(
        Position(0, 0, 0, 90),
        Position(30, 0, 0, 220)
    )

    assert math.isclose(vertical_speed, -7924, abs_tol=1)
