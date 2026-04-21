import type { Flight, FlightWithWind, NavigationWaypoint } from '../types/flight';
import type { VisualizationDataProvider } from '../types/visualization-data-provider';
import type { ApiMTCDEventStructure } from '../types/api-mtcd-event';
import { BlueSkyApiProvider } from './blue-sky-api-provider';
import { DatabaseApiProvider } from './database-api-provider';

/**
 * Represents data communication between js client and BlueSky simulation backend
 */
export class BlueSkyDataProvider implements VisualizationDataProvider {
  private readonly blueSkyApiProvider: BlueSkyApiProvider;
  private readonly databaseApiProvider: DatabaseApiProvider;

  constructor(
    blueSkyApiProvider?: BlueSkyApiProvider,
    databaseApiProvider?: DatabaseApiProvider,
  ) {
    this.blueSkyApiProvider = blueSkyApiProvider ?? new BlueSkyApiProvider();
    this.databaseApiProvider = databaseApiProvider ?? new DatabaseApiProvider();
  }

  /**
   * Adds new flight into the simulation
   * @param flight
   */
  public async createFlight(flight: Flight): Promise<void> {
    await this.blueSkyApiProvider.createFlight(flight);
    if (flight.route && flight.route.length > 0) {
      for (const waypoint of flight.route) {
        await this.addNavigationWaypoint(flight.flightID, waypoint);
      }
    }
  }

  /**
   * Adds a navigation waypoint to a flight's flight plan
   * @param flightId ID of the flight
   * @param navigationWaypoint NavigationWaypoint to add
   */
  public async addNavigationWaypoint(
    flightId: string,
    navigationWaypoint: NavigationWaypoint,
  ): Promise<void> {
    await this.blueSkyApiProvider.addNavigationWaypoint(flightId, navigationWaypoint);
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
  public async setWind(
    heading: number,
    speed: number,
    lat: number,
    lon: number,
    altitude: number,
  ): Promise<void> {
    await this.blueSkyApiProvider.setWind(heading, speed, lat, lon, altitude);
  }

  /**
   * Get current simulation speed
   *
   * @returns Promise that resolves to current speed multiplier value
   */
  public async getSimulationSpeed(): Promise<number> {
    return this.blueSkyApiProvider.getSimulationSpeed();
  }

  /**
   * Set simulation speed by increasing or decreasing by 1 unit
   *
   * @param increase true to increase speed, false to decrease
   * @returns Promise that resolves to current speed multiplier value
   */
  public async setSimulationSpeed(increase: boolean): Promise<number> {
    return this.blueSkyApiProvider.setSimulationSpeed(increase);
  }

  /**
   * Get updated data about all flights
   */
  public async updateFlights(): Promise<FlightWithWind[]> {
    return this.databaseApiProvider.updateFlights();
  }

  /**
   * Stops simulation and removes all flights from simulation
   */
  public async resetSimulation(): Promise<void> {
    await this.databaseApiProvider.resetForNewSimulation();
    return this.blueSkyApiProvider.resetSimulation();
  }

  /**
   * Get all currently active MTCD events from database
   */
  public async getMTCDEvents(): Promise<ApiMTCDEventStructure[]> {
    return this.databaseApiProvider.getMTCDEvents();
  }

  /**
   * Get all MTCD events from database (active and inactive)
   */
  public async getAllMTCDEvents(): Promise<ApiMTCDEventStructure[]> {
    return this.databaseApiProvider.getAllMTCDEvents();
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
    return this.databaseApiProvider.getWaypointCoordinates(name, lat, lon);
  }
}
