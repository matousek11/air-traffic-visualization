import type { Flight, FlightWithWind, Position, NavigationWaypoint } from '../types/flight';

export type ApiFlightStructure = {
  flight_id: string;
  plane_type: string;
  lat: number;
  lon: number;
  heading: number;
  flight_level: number;
  speed: number;
  vertical_speed: number;
  target_flight_level: number | null;
  flight_plan: Array<{ name: string; flight_level: number; speed: number }>;
  wind: { heading: number; speed: number; lat: number; lon: number; altitude: number };
};

export type ApiMTCDEventStructure = {
  id: number;
  flight_id_1: string;
  flight_id_2: string;
  detected_at: string; // ISO datetime string
  horizontal_distance: number | null;
  vertical_distance: number | null;
  remaining_time: number | null;
  middle_point_lat: number | null;
  middle_point_lon: number | null;
  active: boolean;
  last_checked: string | null; // ISO datetime string
};

/**
 * Represents data communication between js client and BlueSky simulation backend
 */
export class BlueSkyDataProvider {
  static readonly BASE_URL = 'http://localhost:8001';
  static readonly DATABASE_API_BASE_URL = 'http://localhost:8002';

  /**
   * Adds new flight into the simulation
   * @param flight
   */
  public async createFlight(flight: Flight): Promise<void> {
    try {
      const response = await fetch(BlueSkyDataProvider.BASE_URL + '/flights', {
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

      const data = await response.json();
      console.log('create flight response:', data);

      // Add waypoints from route if provided
      if (flight.route && flight.route.length > 0) {
        for (const waypoint of flight.route) {
          await this.addNavigationWaypoint(flight.flightID, waypoint);
        }
      }
    } catch (error) {
      console.error('Error making request:', error);
      throw error;
    }
  }

  /**
   * Adds a navigation waypoint to a flight's flight plan
   * @param flightId ID of the flight
   * @param navigationWaypoint NavigationWaypoint to add
   */
  public async addNavigationWaypoint(
    flightId: string,
    navigationWaypoint: NavigationWaypoint
  ): Promise<void> {
    try {
      const response = await fetch(
        `${BlueSkyDataProvider.BASE_URL}/flights/${flightId}/waypoints`,
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

      const data = await response.json();
      console.log('add waypoint response:', data);
    } catch (error) {
      console.error('Error adding waypoint:', error);
      throw error;
    }
  }

  /**
   * Set wind to simulation
   *
   * @param heading in degrees
   * @param speed in kts
   * @param lat latitude
   * @param lon longitude
   * @param altitude in feet
   */
  public async setWind(heading: number, speed: number, lat: number, lon: number, altitude: number): Promise<void> {
    try {
      const response = await fetch(BlueSkyDataProvider.BASE_URL + '/simulation/wind', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          heading: heading,
          speed: speed,
          lat: lat,
          lon: lon,
          altitude: altitude,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log('create wind response:', data);
    } catch (error) {
      console.error('Error making request:', error);
    }
  }

  /**
   * Get current simulation speed
   *
   * @returns Promise that resolves to current speed multiplier value
   */
  public async getSimulationSpeed(): Promise<number> {
    try {
      const response = await fetch(BlueSkyDataProvider.BASE_URL + '/simulation/speed');

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return data.current_speed;
    } catch (error) {
      console.error('Error getting simulation speed:', error);
      throw error;
    }
  }

  /**
   * Set simulation speed by increasing or decreasing by 1 unit
   *
   * @param increase true to increase speed, false to decrease
   * @returns Promise that resolves to current speed multiplier value
   */
  public async setSimulationSpeed(increase: boolean): Promise<number> {
    try {
      const response = await fetch(BlueSkyDataProvider.BASE_URL + '/simulation/speed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          increase: increase,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log('set simulation speed response:', data);
      return data.current_speed;
    } catch (error) {
      console.error('Error setting simulation speed:', error);
      throw error;
    }
  }

  /**
   * Get updated data about all flights
   */
  public async updateFlights(): Promise<FlightWithWind[]> {
    try {
      const response = await fetch(BlueSkyDataProvider.BASE_URL + '/flights');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const apiFlights: ApiFlightStructure[] = await response.json();
      return Promise.all(
        apiFlights.map((apiFlight) => this.mapApiFlightToFlight(apiFlight)),
      );
    } catch (error) {
      console.error('Error updating flights:', error);
      throw error;
    }
  }

  /**
   * Stops simulation and removes all flights from simulation
   */
  public async resetSimulation(): Promise<void> {
    try {
      const response = await fetch(
        BlueSkyDataProvider.BASE_URL + '/reset-simulation',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        },
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
    } catch (error) {
      console.error('Error resetting simulation:', error);
      throw error;
    }
  }

  /**
   * Get all currently active MTCD events from database
   */
  public async getMTCDEvents(): Promise<ApiMTCDEventStructure[]> {
    try {
      const response = await fetch(
        BlueSkyDataProvider.DATABASE_API_BASE_URL + '/mtcd-events',
      );
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const mtcdEvents: ApiMTCDEventStructure[] = await response.json();
      return mtcdEvents;
    } catch (error) {
      console.error('Error fetching MTCD events:', error);
      throw error;
    }
  }

  /**
   * Get all MTCD events from database (active and inactive)
   */
  public async getAllMTCDEvents(): Promise<ApiMTCDEventStructure[]> {
    try {
      const response = await fetch(
        BlueSkyDataProvider.DATABASE_API_BASE_URL + '/mtcd-events?active_only=false',
      );
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const mtcdEvents: ApiMTCDEventStructure[] = await response.json();
      return mtcdEvents;
    } catch (error) {
      console.error('Error fetching all MTCD events:', error);
      throw error;
    }
  }

  /**
   * Gets waypoint coordinates from database service
   *
   * @param name Waypoint name/identifier
   * @param lat Latitude of aircraft position
   * @param lon Longitude of aircraft position
   * @returns Promise resolving to coordinates or null if not found
   */
  public async getWaypointCoordinates(
    name: string,
    lat: number,
    lon: number,
  ): Promise<{ lat: number; lon: number } | null> {
    try {
      const url = `${BlueSkyDataProvider.DATABASE_API_BASE_URL}/waypoints/${encodeURIComponent(name)}?lat=${lat}&lon=${lon}`;

      const response = await fetch(url);

      if (!response.ok) {
        if (response.status === 404) {
          return null;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return { lat: data.lat, lon: data.lon };
    } catch (error) {
      console.error(`Error fetching waypoint coordinates for ${name}:`, error);
      return null;
    }
  }

  /**
   * Converts Flight structure from API response to JS client FlightWithWind
   *
   * @param api_flight Data to be converted into JS structure
   */
  private async mapApiFlightToFlight(api_flight: ApiFlightStructure): Promise<FlightWithWind> {
    const currentPos: Position = [api_flight.lat, api_flight.lon];
    api_flight.wind.speed = Math.trunc(api_flight.wind.speed)

    // Get waypoint coordinates if flight_plan exists
    let flightPlan: NavigationWaypoint[] | undefined = undefined;
    if (api_flight.flight_plan && api_flight.flight_plan.length > 0) {
      flightPlan = await Promise.all(
        api_flight.flight_plan.map(async (waypoint) => {
          const coords = await this.getWaypointCoordinates(
            waypoint.name,
            api_flight.lat,
            api_flight.lon,
          );
          
          return {
            name: waypoint.name,
            flight_level: waypoint.flight_level,
            speed: waypoint.speed,
            ...(coords ? { lat: coords.lat, lon: coords.lon } : {}),
          };
        }),
      );
    }

    const result: FlightWithWind = {
      flightID: api_flight.flight_id,
      planeType: api_flight.plane_type,
      planePosition: {
        speed: api_flight.speed,
        vertical_speed: api_flight.vertical_speed,
        heading: api_flight.heading,
        target_flight_level: api_flight.target_flight_level,
        height: api_flight.flight_level * 100,
        position: currentPos,
      },
      flightPositions: [currentPos],
      wind: api_flight.wind,
    };

    if (flightPlan !== undefined) {
      result.flightPlan = flightPlan;
    }

    return result;
  }
}
