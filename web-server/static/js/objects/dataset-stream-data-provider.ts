import type { FlightWithWind } from '../types/flight';
import type { ApiMTCDEventStructure } from '../types/api-mtcd-event';
import type { VisualizationDataProvider } from '../types/visualization-data-provider';
import type {
  DatasetImportJson,
  ReplayStatusJson,
} from './dataset-replay-api-provider';
import { DatasetReplayApiProvider } from './dataset-replay-api-provider';
import { DatabaseApiProvider } from './database-api-provider';

/**
 * Adapter between dataset stream provider and client
 */
export class DatasetStreamDataProvider implements VisualizationDataProvider {
  private readonly datasetReplayApiProvider: DatasetReplayApiProvider;
  private readonly databaseApiProvider: DatabaseApiProvider;

  constructor() {
    this.datasetReplayApiProvider = new DatasetReplayApiProvider();
    this.databaseApiProvider = new DatabaseApiProvider();
  }

  /**
   * Lists dataset stems available for import.
   */
  public async getImportOptions(): Promise<string[]> {
    return this.datasetReplayApiProvider.getImportOptions();
  }

  /**
   * Imports one dataset CSV into the dataset table.
   */
  public async importDataset(datasetName: string): Promise<DatasetImportJson> {
    return this.datasetReplayApiProvider.importDataset(datasetName);
  }

  /**
   * Starts replay worker.
   */
  public async startReplay(
    speed: number,
    tickIntervalSeconds: number,
  ): Promise<ReplayStatusJson> {
    return this.datasetReplayApiProvider.startReplay(speed, tickIntervalSeconds);
  }

  /**
   * Stops replay worker.
   */
  public async stopReplay(): Promise<ReplayStatusJson> {
    return this.datasetReplayApiProvider.stopReplay();
  }

  /**
   * Stops replay stream then clears application flight tables in database-service.
   */
  public async resetSimulation(): Promise<void> {
    await this.datasetReplayApiProvider.stopReplay();
    await this.databaseApiProvider.resetForNewSimulation();
  }

  /**
   * Current replay speed of dataset.
   */
  public async getSimulationSpeed(): Promise<number> {
    return this.datasetReplayApiProvider.getSimulationSpeed();
  }

  /**
   * Step replay speed up or down.
   */
  public async setSimulationSpeed(increase: boolean): Promise<number> {
    return this.datasetReplayApiProvider.setSimulationSpeed(increase);
  }

  public async updateFlights(): Promise<FlightWithWind[]> {
    return this.databaseApiProvider.updateFlights();
  }

  public async getMTCDEvents(): Promise<ApiMTCDEventStructure[]> {
    return this.databaseApiProvider.getMTCDEvents();
  }

  public async getAllMTCDEvents(): Promise<ApiMTCDEventStructure[]> {
    return this.databaseApiProvider.getAllMTCDEvents();
  }

  public async getWaypointCoordinates(
    name: string,
    lat: number,
    lon: number,
  ): Promise<{ lat: number; lon: number } | null> {
    return this.databaseApiProvider.getWaypointCoordinates(name, lat, lon);
  }
}
