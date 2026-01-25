import scenarios from '../../config/simulation-scenarios.json';
import { SimulationScenarios } from './simulation-scenarios';

/**
 * Callback type for scenario selection events
 */
type ScenarioSelectedCallback = (scenarioName: string) => void;

/**
 * Callback type for stop simulation events
 */
type StopSimulationCallback = () => void;

/**
 * Class responsible for creating and managing a modal dialog
 * that displays available simulation scenarios and allows the user to select one.
 */
export class ScenarioModal {
  private readonly modalOverlay: HTMLDivElement;
  private readonly modalContent: HTMLDivElement;
  private readonly simulationScenarios: SimulationScenarios;
  private onScenarioSelected: ScenarioSelectedCallback | null = null;
  private onStopSimulation: StopSimulationCallback | null = null;

  /**
   * Creates a new ScenarioModal instance and builds the modal DOM elements
   */
  constructor() {
    this.simulationScenarios = new SimulationScenarios(scenarios);
    this.modalOverlay = this.createModalOverlay();
    this.modalContent = this.createModalContent();
    this.buildModal();
  }

  /**
   * Creates the modal overlay element that covers the entire screen
   *
   * @returns The modal overlay div element
   */
  private createModalOverlay(): HTMLDivElement {
    const overlay = document.createElement('div');
    overlay.id = 'scenario-modal-overlay';
    overlay.className = 'scenario-modal-overlay';
    overlay.addEventListener('click', (e: MouseEvent): void => {
      if (e.target === overlay) {
        this.hide();
      }
    });
    return overlay;
  }

  /**
   * Creates the modal content container element
   *
   * @returns The modal content div element
   */
  private createModalContent(): HTMLDivElement {
    const content = document.createElement('div');
    content.className = 'scenario-modal-content';
    return content;
  }

  /**
   * Builds the complete modal structure with header, scenario buttons, and stop button
   */
  private buildModal(): void {
    // Create header
    const header = document.createElement('h2');
    header.className = 'scenario-modal-header';
    header.textContent = 'Select Simulation Scenario';
    this.modalContent.appendChild(header);

    // Create buttons container
    const buttonsContainer = document.createElement('div');
    buttonsContainer.className = 'scenario-modal-buttons';

    // Create button for each scenario
    const scenarioNames = this.simulationScenarios.getScenarioNames();
    scenarioNames.forEach((scenarioName: string): void => {
      const scenario = this.simulationScenarios.getScenario(scenarioName);
      const button = this.createScenarioButton(scenarioName, scenario.name);
      buttonsContainer.appendChild(button);
    });

    // Create stop simulation button
    const stopButton = this.createStopButton();
    buttonsContainer.appendChild(stopButton);

    this.modalContent.appendChild(buttonsContainer);
    this.modalOverlay.appendChild(this.modalContent);
    document.body.appendChild(this.modalOverlay);
  }

  /**
   * Creates a button element for a specific scenario
   *
   * @param scenarioKey The key/identifier of the scenario
   * @param scenarioDisplayName The human-readable name of the scenario
   * @returns The created button element
   */
  private createScenarioButton(
    scenarioKey: string,
    scenarioDisplayName: string,
  ): HTMLButtonElement {
    const button = document.createElement('button');
    button.className = 'scenario-modal-button scenario-button';
    button.textContent = scenarioDisplayName;
    button.addEventListener('click', (): void => {
      this.handleScenarioClick(scenarioKey);
    });
    return button;
  }

  /**
   * Creates the stop simulation button
   *
   * @returns The created stop button element
   */
  private createStopButton(): HTMLButtonElement {
    const button = document.createElement('button');
    button.className = 'scenario-modal-button stop-button';
    button.textContent = 'Stop Simulation';
    button.addEventListener('click', (): void => {
      this.handleStopClick();
    });
    return button;
  }

  /**
   * Handles click events on scenario buttons
   *
   * @param scenarioKey The key of the selected scenario
   */
  private handleScenarioClick(scenarioKey: string): void {
    if (this.onScenarioSelected) {
      this.onScenarioSelected(scenarioKey);
    }
    this.hide();
  }

  /**
   * Handles click events on the stop simulation button
   */
  private handleStopClick(): void {
    if (this.onStopSimulation) {
      this.onStopSimulation();
    }
    this.hide();
  }

  /**
   * Displays the modal overlay
   */
  public show(): void {
    this.modalOverlay.classList.add('visible');
  }

  /**
   * Hides the modal overlay
   */
  public hide(): void {
    this.modalOverlay.classList.remove('visible');
  }

  /**
   * Registers a callback to be called when a scenario is selected
   *
   * @param callback Function to be called with the scenario key when selected
   */
  public setOnScenarioSelected(callback: ScenarioSelectedCallback): void {
    this.onScenarioSelected = callback;
  }

  /**
   * Registers a callback to be called when stop simulation is clicked
   *
   * @param callback Function to be called when stop is clicked
   */
  public setOnStopSimulation(callback: StopSimulationCallback): void {
    this.onStopSimulation = callback;
  }
}
