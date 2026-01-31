import type { Flight, FlightWithWind, Position } from '../types/flight';

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
    } catch (error) {
      console.error('Error making request:', error);
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
      return apiFlights.map((apiFlight) =>
        this.mapApiFlightToFlight(apiFlight),
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
   * Converts Flight structure from API response to JS client FlightWithWind
   *
   * @param api_flight Data to be converted into JS structure
   */
  private mapApiFlightToFlight(api_flight: ApiFlightStructure): FlightWithWind {
    const currentPos: Position = [api_flight.lat, api_flight.lon];
    api_flight.wind.speed = Math.trunc(api_flight.wind.speed)

    return {
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
      wind: api_flight.wind
    };
  }
}
