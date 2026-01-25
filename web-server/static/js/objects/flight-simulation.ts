import type { Flight } from '../types/flight';
import scenarios from '../../config/simulation-scenarios.json';
import { SimulationScenarios } from './simulation-scenarios';
import { BlueSkyDataProvider } from './blue-sky-data-provider';

/**
 * Used for control of BlueSky simulation
 */
export class FlightSimulation {
  private blueSkyDataProvider: BlueSkyDataProvider;

  constructor() {
    this.blueSkyDataProvider = new BlueSkyDataProvider();
  }

  /**
   * Get the newest data about flights from data provider
   */
  public async updateFlights(): Promise<Flight[]> {
    return this.blueSkyDataProvider.updateFlights();
  }

  /**
   * Resets simulation on current data provider
   */
  public resetSimulation(): void {
    void this.blueSkyDataProvider.resetSimulation();
  }

  /**
   * Loads a scenario into the simulation by name
   *
   * @param scenarioName Name of the scenario to load from scenarios JSON
   */
  public loadScenario(scenarioName: string): void {
    const checkedScenarios = new SimulationScenarios(scenarios);
    const scenario = checkedScenarios.getScenario(scenarioName);

    scenario.flights.forEach(
      (flight): Promise<void> => this.blueSkyDataProvider.createFlight(flight),
    );
  }
}
