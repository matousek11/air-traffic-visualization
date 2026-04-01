/** Response shape for GET /replay/status and POST /replay/speed, POST /replay/stop. */
export type ReplayStatusJson = {
  running: boolean;
  speed: number;
  tick_interval_seconds: number;
};

/** Response for POST /datasets/{name}/import. */
export type DatasetImportJson = {
  dataset_name: string;
  table_name: string;
  rows_imported: number;
  rows_skipped: number;
};

/**
 * HTTP wrapper for dataset_stream replay and import endpoints.
 */
export class DatasetReplayApiProvider {
  static readonly BASE_URL = 'http://localhost:8010';

  /**
   * Lists dataset stems available for import.
   *
   * @returns Dataset names
   */
  public async getImportOptions(): Promise<string[]> {
    const response = await fetch(
      `${DatasetReplayApiProvider.BASE_URL}/datasets/import-options`,
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json() as Promise<string[]>;
  }

  /**
   * Imports one dataset CSV into the dataset table.
   *
   * @param datasetName Dataset stem name
   *
   * @returns Import result payload
   */
  public async importDataset(datasetName: string): Promise<DatasetImportJson> {
    const response = await fetch(
      `${DatasetReplayApiProvider.BASE_URL}/datasets/${encodeURIComponent(datasetName)}/import`,
      { method: 'POST' },
    );

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Import failed: ${response.status} ${detail}`);
    }

    return await response.json() as Promise<DatasetImportJson>;
  }

  /**
   * Starts replay worker.
   *
   * @param speed Replay speed multiplier
   * @param tickIntervalSeconds Replay tick interval in seconds
   *
   * @returns Replay status payload
   */
  public async startReplay(
    speed: number,
    tickIntervalSeconds: number,
  ): Promise<ReplayStatusJson> {
    const response = await fetch(`${DatasetReplayApiProvider.BASE_URL}/replay/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        speed,
        tick_interval_seconds: tickIntervalSeconds,
      }),
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`Replay start failed: ${response.status} ${detail}`);
    }

    return await response.json() as Promise<ReplayStatusJson>;
  }

  /**
   * Stops replay worker.
   *
   * @returns Replay status payload
   */
  public async stopReplay(): Promise<ReplayStatusJson> {
    const response = await fetch(`${DatasetReplayApiProvider.BASE_URL}/replay/stop`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json() as Promise<ReplayStatusJson>;
  }

  /**
   * Current replay speed from replay status endpoint.
   *
   * @returns Current speed multiplier
   */
  public async getSimulationSpeed(): Promise<number> {
    const response = await fetch(`${DatasetReplayApiProvider.BASE_URL}/replay/status`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = (await response.json()) as ReplayStatusJson;
    return data.speed;
  }

  /**
   * Step replay speed up or down.
   *
   * @param increase True to increase speed, false to decrease
   *
   * @returns Current speed multiplier
   */
  public async setSimulationSpeed(increase: boolean): Promise<number> {
    const response = await fetch(`${DatasetReplayApiProvider.BASE_URL}/replay/speed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ increase }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = (await response.json()) as ReplayStatusJson;
    return data.speed;
  }
}
