import scenarios from '../../config/simulation-scenarios.json';
import { MapUi } from './map-ui';
import { SelectionModal } from './selection-modal';
import { SimulationScenarios } from './simulation-scenarios';

/**
 * Entry class for client web application.
 */
export class AirTrafficVisualization {
  private readonly mapUi: MapUi;
  private readonly scenarioModal: SelectionModal;
  private readonly dataSourceModal: SelectionModal;
  private readonly simulationScenarios: SimulationScenarios;
  private currentSpeed: number = 1.0;
  private currentDataSourceId: string = 'bluesky';

  /**
   * Automatically initialize web UI
   */
  constructor() {
    this.mapUi = new MapUi();
    this.simulationScenarios = new SimulationScenarios(scenarios);

    const scenarioOptions = this.simulationScenarios.getScenarioNames().map(
      (key): { id: string; label: string } => ({
        id: key,
        label: this.simulationScenarios.getScenario(key).name,
      }),
    );

    this.scenarioModal = new SelectionModal({
      title: 'Simulation Scenario',
      options: scenarioOptions,
      variant: 'scenario',
      overlayId: 'scenario-modal-overlay',
      extraButton: {
        label: 'Stop Simulation',
        callback: (): void => this.stopSimulation(),
      },
      onSelect: (scenarioName: string): void => this.onScenarioSelected(scenarioName),
    });

    this.dataSourceModal = new SelectionModal({
      title: 'Data source',
      options: [
        { id: 'bluesky', label: 'BlueSky' },
        { id: 'live', label: 'Live data' },
      ],
      activeId: 'bluesky',
      variant: 'dataSource',
      overlayId: 'data-source-modal-overlay',
      onSelect: (id: string): void => {
        void this.onDataSourceSelected(id);
      },
    });

    this.initHandlers();
    this.loadSimulationSpeed();
    void this.mapUi.resumeVisualizationIfFlightsExist();
  }

  /**
   * Handles scenario or dataset selection depending on an active data source.
   *
   * @param scenarioName Scenario key from JSON or dataset stem for live mode.
   */
  private onScenarioSelected(scenarioName: string): void {
    switch (this.currentDataSourceId) {
      case 'live':
        void this.startLiveDatasetStreaming(scenarioName);
        break;
      case 'bluesky':
        this.startBlueSkyScenario(scenarioName);
        break;
    }
  }

  /**
   * Switches a data source: providers, scenario list, and polling.
   *
   * @param id `bluesky` or `live`.
   */
  private async onDataSourceSelected(id: string): Promise<void> {
    this.currentDataSourceId = id;
    switch (id) {
      case 'live':
        await this.applyLiveDataSource();
        break;
      case 'bluesky':
        await this.applyBlueSkyDataSource();
        break;
    }
  }

  /**
   * Configures live mode: dataset list in scenario modal, dataset-stream provider active.
   */
  private async applyLiveDataSource(): Promise<void> {
    this.mapUi.useDatasetStreamVisualization();
    void this.mapUi.getDatasetStreamDataProvider().stopReplay().catch((): void => {
      /* ignore if not running */
    });
    this.mapUi.stopSimulation();

    try {
      const names = await this.mapUi.getDatasetStreamDataProvider().getImportOptions();
      const opts = names.map((n): { id: string; label: string } => ({
        id: n,
        label: n,
      }));
      this.scenarioModal.setOptions(opts, 'Dataset');
    } catch (error) {
      console.error('Failed to load dataset list:', error);
    }

    this.loadSimulationSpeed();
  }

  /**
   * Restores BlueSky scenario list and visualization provider.
   */
  private async applyBlueSkyDataSource(): Promise<void> {
    try {
      await this.mapUi.getDatasetStreamDataProvider().stopReplay();
    } catch (error) {
      console.error('Stop replay:', error);
    }

    this.mapUi.useBlueSkyVisualization();
    this.mapUi.stopSimulation();
    const scenarioOptions = this.simulationScenarios.getScenarioNames().map(
      (key): { id: string; label: string } => ({
        id: key,
        label: this.simulationScenarios.getScenario(key).name,
      }),
    );
    this.scenarioModal.setOptions(scenarioOptions, 'Simulation Scenario');
    this.loadSimulationSpeed();
  }

  /**
   * Load current simulation speed from the server and update the display
   */
  private loadSimulationSpeed(): void {
    void this.mapUi.getSimulationSpeed().then((speed: number): void => {
      this.currentSpeed = speed;
      this.mapUi.updateSpeedDisplay(this.currentSpeed);
    }).catch((error: Error): void => {
      console.error('Error loading simulation speed:', error);
      // Keep default value if request fails
      this.mapUi.updateSpeedDisplay(this.currentSpeed);
    });
  }

  /**
   * Prepare event listeners for UI actions
   */
  private initHandlers(): void {
    const uiHandlers: Record<string, () => void> = {
      'bottom-left-button': () => this.openScenarioModal(),
      'data-source-button': () => this.dataSourceModal.show(),
      'speed-decrease': () => this.decreaseSpeed(),
      'speed-increase': () => this.increaseSpeed(),
      'heatmap-toggle': () => this.toggleHeatmap(),
    };

    Object.entries(uiHandlers).forEach(([elementId, handler]): void => {
      this.bindButton(elementId, handler);
    });
  }

  /**
   * Toggle heatmap on/off and update the heatmap button label and style.
   */
  private toggleHeatmap(): void {
    const enabled = !this.mapUi.getHeatmapEnabled();
    this.mapUi.setHeatmapEnabled(enabled);
    this.updateHeatmapButton(enabled);
  }

  /**
   * Update heatmap toggle button text and class (red when off, green when on).
   */
  private updateHeatmapButton(enabled: boolean): void {
    const button = document.getElementById('heatmap-toggle');
    if (button === null) {
      return;
    }
    
    button.textContent = enabled ? 'Heatmap on' : 'Heatmap off';
    button.classList.remove('heatmap-off', 'heatmap-on');
    button.classList.add(enabled ? 'heatmap-on' : 'heatmap-off');
  }

  /**
   * Bind handler to click event on element
   *
   * @param elementId ID of the HTML element to bind
   * @param handler Function to be called on click
   *
   * @throws Error When HTML element with buttonID doesn't exist
   */
  private bindButton(elementId: string, handler: () => void): void {
    const button: HTMLElement | null = document.getElementById(elementId);
    if (button === null) {
      throw Error(`Button with ID ${elementId} doesn't exist in HTML.`);
    }

    button.addEventListener('click', handler);
  }

  /**
   * Opens the scenario selection modal
   */
  private async openScenarioModal(): Promise<void> {
    if (this.currentDataSourceId === 'live') {
      try {
        const names = await this.mapUi
          .getDatasetStreamDataProvider()
          .getImportOptions();
        this.scenarioModal.setOptions(
          names.map((n): { id: string; label: string } => ({
            id: n,
            label: n,
          })),
          'Dataset',
        );
      } catch (error) {
        console.error('Failed to refresh datasets:', error);
      }
    }
    this.scenarioModal.show();
  }

  /**
   * Starts the selected simulation scenario
   *
   * @param scenarioName Name of the scenario to start
   */
  private startBlueSkyScenario(scenarioName: string): void {
    void this.mapUi.startBlueSkyScenario(scenarioName).catch((error: Error) => {
      console.error('Failed to start scenario:', error);
    });
  }

  /**
   * Starts streaming of selected dataset and prepares the client for incoming data.
   *
   * @param datasetName Dataset stem from import-options.
   */
  private async startLiveDatasetStreaming(datasetName: string): Promise<void> {
    const ds = this.mapUi.getDatasetStreamDataProvider();
    try {
      await ds.resetSimulation();
      await ds.importDataset(datasetName);
      await ds.startReplay(1, 5);
      this.mapUi.useDatasetStreamVisualization();
      this.mapUi.uiUpdateLoop();
      this.loadSimulationSpeed();
    } catch (error) {
      console.error('Live dataset pipeline failed:', error);
      window.alert(
        `Failed to start dataset: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  }

  /**
   * Stops the current simulation
   */
  private stopSimulation(): void {
    if (this.currentDataSourceId === 'live') {
      void this.mapUi.getDatasetStreamDataProvider().stopReplay();
    }
    this.mapUi.stopSimulation();
  }

  /**
   * Decreases simulation speed by 1 unit
   */
  private decreaseSpeed(): void {
    void this.mapUi.setSimulationSpeed(false).then((speed: number): void => {
      this.currentSpeed = speed;
      this.mapUi.updateSpeedDisplay(this.currentSpeed);
    }).catch((error: Error): void => {
      console.error('Error decreasing speed:', error);
    });
  }

  /**
   * Increases simulation speed by 1 unit
   */
  private increaseSpeed(): void {
    void this.mapUi.setSimulationSpeed(true).then((speed: number): void => {
      this.currentSpeed = speed;
      this.mapUi.updateSpeedDisplay(this.currentSpeed);
    }).catch((error: Error): void => {
      console.error('Error increasing speed:', error);
    });
  }
}
