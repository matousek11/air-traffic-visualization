import type { Flight, NavigationWaypoint } from '../types/flight';

/**
 * HTTP client wrapper for BlueSky simulation endpoints.
 */
export class BlueSkyApiProvider {
  static readonly BASE_URL = 'http://localhost:8001';

  /**
   * Adds new flight into the simulation.
   *
   * @param flight Flight payload
   */
  public async createFlight(flight: Flight): Promise<void> {
    const response = await fetch(BlueSkyApiProvider.BASE_URL + '/flights', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        flight_id: flight.flightID,
        plane_type: flight.planeType,
        lat: flight.planePosition.position[0],
        lon: flight.planePosition.position[1],
        heading: flight.planePosition.heading,
        flight_level: flight.planePosition.height,
        target_flight_level: flight.planePosition.target_flight_level ?? null,
        speed: flight.planePosition.speed,
        vertical_speed: flight.planePosition.vertical_speed,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  }

  /**
   * Adds a navigation waypoint to a flight's flight plan.
   *
   * @param flightId ID of the flight
   * @param navigationWaypoint Navigation waypoint payload
   */
  public async addNavigationWaypoint(
    flightId: string,
    navigationWaypoint: NavigationWaypoint,
  ): Promise<void> {
    const response = await fetch(
      `${BlueSkyApiProvider.BASE_URL}/flights/${flightId}/waypoints`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: navigationWaypoint.name,
          flight_level: navigationWaypoint.flight_level,
          speed: navigationWaypoint.speed,
        }),
      },
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  }

  /**
   * Set wind to simulation.
   *
   * @param heading Wind heading in degrees
   * @param speed Wind speed in kts
   * @param lat Latitude
   * @param lon Longitude
   * @param altitude Altitude in feet
   */
  public async setWind(
    heading: number,
    speed: number,
    lat: number,
    lon: number,
    altitude: number,
  ): Promise<void> {
    const response = await fetch(BlueSkyApiProvider.BASE_URL + '/simulation/wind', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ heading, speed, lat, lon, altitude }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  }

  /**
   * Get current simulation speed.
   *
   * @returns Current speed multiplier value
   */
  public async getSimulationSpeed(): Promise<number> {
    const response = await fetch(BlueSkyApiProvider.BASE_URL + '/simulation/speed');
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    return data.current_speed as number;
  }

  /**
   * Set the simulation speed by increasing or decreasing by 1 unit.
   *
   * @param increase True to increase speed, false to decrease
   *
   * @returns Current speed multiplier value
   */
  public async setSimulationSpeed(increase: boolean): Promise<number> {
    const response = await fetch(BlueSkyApiProvider.BASE_URL + '/simulation/speed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ increase }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    return data.current_speed as number;
  }

  /**
   * Stops simulation and removes all flights from simulation.
   */
  public async resetSimulation(): Promise<void> {
    const response = await fetch(BlueSkyApiProvider.BASE_URL + '/reset-simulation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  }
}
