import { MapUi } from './map-ui';
import { ScenarioModal } from './scenario-modal';

/**
 * Entry class for client web application.
 */
export class AirTrafficVisualization {
  private readonly mapUi: MapUi;
  private readonly scenarioModal: ScenarioModal;

  /**
   * Automatically initialize web UI
   */
  constructor() {
    this.mapUi = new MapUi();
    this.scenarioModal = new ScenarioModal();
    this.initHandlers();
    this.initModalCallbacks();
  }

  /**
   * Prepare event listeners for UI actions
   */
  private initHandlers(): void {
    const uiHandlers: Record<string, () => void> = {
      'bottom-left-button': () => this.openScenarioModal(),
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
}
