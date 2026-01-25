export type Position = [number, number];

export type PlanePosition = {
  speed: number;
  vertical_speed: number;
  heading: number;
  height: number;
  target_flight_level: number | null;
  position: Position;
};

export type Flight = {
  flightID: string;
  planeType: string;
  planePosition: PlanePosition;
  flightPositions: Position[];
};
