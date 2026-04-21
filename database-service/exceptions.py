"""Domain-specific exceptions for the database service."""


class NavNotFoundError(Exception):
    """Raised when no navigation aid exists for the given lookup."""

    def __init__(self, identification: str, lat: float, lon: float) -> None:
        """Initialize with lookup context.

        Args:
            identification: Requested NAV identificator.
            lat: Latitude used for the search (degrees).
            lon: Longitude used for the search (degrees).
        """
        self.identification = identification
        self.lat = lat
        self.lon = lon
        message = (
            f"No NAV point found for {identification}, "
            f"lat: {lat}, lon: {lon}"
        )
        super().__init__(message)
