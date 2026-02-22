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
  private currentSpeed: number = 1.0;
  private currentDataSourceId: string = 'bluesky';

  /**
   * Automatically initialize web UI
   */
  constructor() {
    this.mapUi = new MapUi();

    const simulationScenarios = new SimulationScenarios(scenarios);
    const scenarioOptions = simulationScenarios.getScenarioNames().map(
      (key): { id: string; label: string } => ({
        id: key,
        label: simulationScenarios.getScenario(key).name,
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
      onSelect: (scenarioName: string): void => this.startScenario(scenarioName),
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
        this.currentDataSourceId = id;
      },
    });

    this.initHandlers();
    this.loadSimulationSpeed();
    void this.mapUi.resumeVisualizationIfFlightsExist();
  }

  /**
   * Load current simulation speed from server and update display
   */
  private loadSimulationSpeed(): void {
    void this.mapUi.getSimulationSpeed().then((speed: number): void => {
      this.currentSpeed = speed;
      this.updateSpeedDisplay();
    }).catch((error: Error): void => {
      console.error('Error loading simulation speed:', error);
      // Keep default value if request fails
      this.updateSpeedDisplay();
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
  private openScenarioModal(): void {
    this.scenarioModal.show();
  }

  /**
   * Starts the selected simulation scenario
   *
   * @param scenarioName Name of the scenario to start
   */
  private startScenario(scenarioName: string): void {
    this.mapUi.startScenario(scenarioName);
  }

  /**
   * Stops the current simulation
   */
  private stopSimulation(): void {
    this.mapUi.stopSimulation();
  }

  /**
   * Decreases simulation speed by 1 unit
   */
  private decreaseSpeed(): void {
    void this.mapUi.setSimulationSpeed(false).then((speed: number): void => {
      this.currentSpeed = speed;
      this.updateSpeedDisplay();
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
      this.updateSpeedDisplay();
    }).catch((error: Error): void => {
      console.error('Error increasing speed:', error);
    });
  }

  /**
   * Updates the speed display element with current speed
   */
  private updateSpeedDisplay(): void {
    const speedDisplay = document.getElementById('speed-display');
    if (speedDisplay !== null) {
      speedDisplay.textContent = `${this.currentSpeed.toFixed(1)}x`;
    }
  }
}
