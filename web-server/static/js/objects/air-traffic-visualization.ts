import { MapUi } from './map-ui';
import { ScenarioModal } from './scenario-modal';

/**
 * Entry class for client web application.
 */
export class AirTrafficVisualization {
  private readonly mapUi: MapUi;
  private readonly scenarioModal: ScenarioModal;
  private currentSpeed: number = 1.0;

  /**
   * Automatically initialize web UI
   */
  constructor() {
    this.mapUi = new MapUi();
    this.scenarioModal = new ScenarioModal();
    this.initHandlers();
    this.initModalCallbacks();
    this.loadSimulationSpeed();
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
      'speed-decrease': () => this.decreaseSpeed(),
      'speed-increase': () => this.increaseSpeed(),
    };

    Object.entries(uiHandlers).forEach(([elementId, handler]): void => {
      this.bindButton(elementId, handler);
    });
  }

  /**
   * Initialize callbacks for the scenario modal
   */
  private initModalCallbacks(): void {
    this.scenarioModal.setOnScenarioSelected(
      (scenarioName: string): void => {
        this.startScenario(scenarioName);
      },
    );

    this.scenarioModal.setOnStopSimulation((): void => {
      this.stopSimulation();
    });
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
