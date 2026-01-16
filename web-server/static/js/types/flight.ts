export type Position = [number, number]

export type PlanePosition = {
    speed: number,
    heading: number,
    height: number
    position: Position
}

export type Flight = {
  flightID: string;
  planeType: string;
  planePosition: PlanePosition;
  flightPositions: Position[];
};