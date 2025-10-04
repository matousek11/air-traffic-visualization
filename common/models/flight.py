"""
House Flight entity from NM B2B
"""
import string

from common.models.plane import Plane


class Flight:
    """
    Represents Flight entity from NM B2B
    """

    def __init__(
            self,
            ipflid: string,
            aircraft_id: string,
            aerodrome_of_departure: string,
            non_icao_aerodrome_of_departure: bool,
            air_filed: bool,
            aerodrome_of_destination: string,
            non_icao_aerodrome_of_destination: bool,
            plane: Plane
    ):
        self.ipflid = ipflid
        self.aircraft_id = aircraft_id
        self.aerodrome_of_departure = aerodrome_of_departure
        self.non_icao_aerodrome_of_departure = non_icao_aerodrome_of_departure
        self.air_filed = air_filed
        self.aerodrome_of_destination = aerodrome_of_destination
        self.non_icao_aerodrome_of_destination = non_icao_aerodrome_of_destination
        self.plane = plane
