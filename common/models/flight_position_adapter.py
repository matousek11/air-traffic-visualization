class FlightPositionAdapter:
    """Adapter to convert FlightPosition from database to Flight-like object for MtcdToolkit."""

    def __init__(self, flight_position, flight_id: str):
        """
        Initialize adapter from FlightPosition.

        Args:
            flight_position: FlightPosition object from database
            flight_id: Flight ID
        """
        self.flight_id = flight_id
        self.lat = flight_position.lat
        self.lon = flight_position.lon
        self.flight_level = flight_position.flight_level if flight_position.flight_level else 0
        self.speed = flight_position.ground_speed_kt
        self.heading = flight_position.heading
        self.track_heading = flight_position.track_heading
        self.route = flight_position.route
        # vertical_speed in ft/min (same as vertical_rate_fpm)
        self.vertical_speed = float(flight_position.vertical_rate_fpm or 0)