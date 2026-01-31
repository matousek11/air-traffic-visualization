export type Position = [number, number];

export type PlanePosition = {
  speed: number;
  vertical_speed: number;
  heading: number;
  height: number;
  target_flight_level: number | null;
  position: Position;
};

export type Wind = {
  heading: number;
  speed: number;
  lat: number;
  lon: number;
  altitude: number;
};

/**
 * Flight data for creating flights (without wind - wind comes from API response)
 */
export type Flight = {
  flightID: string;
  planeType: string;
  planePosition: PlanePosition;
  flightPositions: Position[];
};

/**
 * Flight data returned from API (includes wind at aircraft position)
 */
export type FlightWithWind = Flight & {
  wind: Wind;
};
