import type { ApiMTCDEventStructure } from '../types/api-mtcd-event';
import type {
  FlightPlanDisplayWaypoint,
  FlightWithWind,
  Position,
} from '../types/flight';

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
  flight_plan: string[];
  wind: { heading: number; speed: number; lat: number; lon: number; altitude: number };
};

/**
 * HTTP client wrapper for database-service endpoints.
 */
export class DatabaseApiProvider {
  static readonly BASE_URL = 'http://localhost:8002';
  private readonly waypointCache: Map<string, { lat: number; lon: number } | null> =
    new Map();

  /**
   * Fetches and maps all flights from database API.
   *
   * @returns List of flights with wind data
   */
  public async updateFlights(): Promise<FlightWithWind[]> {
    const response = await fetch(DatabaseApiProvider.BASE_URL + '/flights');

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const apiFlights: ApiFlightStructure[] = await response.json();
    return Promise.all(
      apiFlights.map((apiFlight) => this.mapApiFlightToFlight(apiFlight))
    );
  }

  /**
   * Get all currently active MTCD events from a database.
   *
   * @returns Active MTCD events
   */
  public async getMTCDEvents(): Promise<ApiMTCDEventStructure[]> {
    const response = await fetch(DatabaseApiProvider.BASE_URL + '/mtcd-events');

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json() as Promise<ApiMTCDEventStructure[]>;
  }

  /**
   * Get all MTCD events from the database (active and inactive).
   *
   * @returns All MTCD events
   */
  public async getAllMTCDEvents(): Promise<ApiMTCDEventStructure[]> {
    const response = await fetch(
      DatabaseApiProvider.BASE_URL + '/mtcd-events?active_only=false',
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json() as Promise<ApiMTCDEventStructure[]>;
  }

  /**
   * Gets waypoint coordinates from database service.
   *
   * @param name Waypoint name/identifier
   * @param lat Latitude of aircraft position
   * @param lon Longitude of aircraft position
   *
   * @returns Coordinates or null if not found
   */
  public async getWaypointCoordinates(
    name: string,
    lat: number,
    lon: number,
  ): Promise<{ lat: number; lon: number } | null> {
    const cacheKey = this.buildWaypointCacheKey(name, lat, lon);
    if (this.waypointCache.has(cacheKey)) {
      return this.waypointCache.get(cacheKey) ?? null;
    }

    try {
      const url = `${DatabaseApiProvider.BASE_URL}/waypoints/${encodeURIComponent(name)}?lat=${lat}&lon=${lon}`;
      const response = await fetch(url);

      if (!response.ok) {
        if (response.status === 404) {
          this.waypointCache.set(cacheKey, null);
          return null;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      const coordinates = { lat: data.lat as number, lon: data.lon as number };
      this.waypointCache.set(cacheKey, coordinates);

      return coordinates;
    } catch (error) {
      console.error(`Error fetching waypoint coordinates for ${name}:`, error);
      return null;
    }
  }

  /**
   * Clears application flight tables in database-service.
   */
  public async resetForNewSimulation(): Promise<void> {
    const response = await fetch(DatabaseApiProvider.BASE_URL + '/reset-for-new-simulation', {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  }

  /**
   * Converts API flight structure into UI FlightWithWind.
   *
   * @param apiFlight Raw API flight payload
   * @returns Flight with optional mapped flight plan coordinates
   */
  private async mapApiFlightToFlight(apiFlight: ApiFlightStructure): Promise<FlightWithWind> {
    const currentPos: Position = [apiFlight.lat, apiFlight.lon];
    apiFlight.wind.speed = Math.trunc(apiFlight.wind.speed);

    let flightPlan: FlightPlanDisplayWaypoint[] | undefined;
    if (apiFlight.flight_plan && apiFlight.flight_plan.length > 0) {
      flightPlan = await Promise.all(
        apiFlight.flight_plan.map(async (name) => {
          const coords = await this.getWaypointCoordinates(name, apiFlight.lat, apiFlight.lon);
          return {
            name,
            ...(coords ? { lat: coords.lat, lon: coords.lon } : {}),
          };
        }),
      );
    }

    const result: FlightWithWind = {
      flightID: apiFlight.flight_id,
      planeType: apiFlight.plane_type,
      planePosition: {
        speed: apiFlight.speed,
        vertical_speed: apiFlight.vertical_speed,
        heading: apiFlight.heading,
        target_flight_level: apiFlight.target_flight_level,
        height: apiFlight.flight_level * 100,
        position: currentPos,
      },
      flightPositions: [currentPos],
      wind: apiFlight.wind,
    };

    if (flightPlan !== undefined) {
      result.flightPlan = flightPlan;
    }

    return result;
  }

  /**
   * Builds cache key for waypoint nearest-position lookup.
   *
   * @param name Waypoint identifier
   * @param lat Aircraft latitude used for nearest selection
   * @param lon Aircraft longitude used for nearest selection
   * @returns Stable cache key string
   */
  private buildWaypointCacheKey(name: string, lat: number, lon: number): string {
    const roundedLat = Math.round(lat * 10) / 10;
    const roundedLon = Math.round(lon * 10) / 10;
    return `${name}|${roundedLat}|${roundedLon}`;
  }
}
