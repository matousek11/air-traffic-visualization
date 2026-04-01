import type { ApiMTCDEventStructure } from './api-mtcd-event';
import type { FlightWithWind } from './flight';

/**
 * API interface for data providers visualization.
 */
export interface VisualizationDataProvider {
  getSimulationSpeed(): Promise<number>;
  setSimulationSpeed(increase: boolean): Promise<number>;
  updateFlights(): Promise<FlightWithWind[]>;
  getMTCDEvents(): Promise<ApiMTCDEventStructure[]>;
  getAllMTCDEvents(): Promise<ApiMTCDEventStructure[]>;
  getWaypointCoordinates(
    name: string,
    lat: number,
    lon: number,
  ): Promise<{ lat: number; lon: number } | null>;
  resetSimulation(): Promise<void>;
}
