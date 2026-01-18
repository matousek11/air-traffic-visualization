import type {Flight} from "../types/flight";
import scenarios from "../../config/simulation-scenarios.json"
import {SimulationScenarios} from "./simulation-scenarios";
import {BlueSkyDataProvider} from "./blue-sky-data-provider";

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
     * Loads scenario into simulation from scenarios json
     *
     * @param scenarioName scenario that should be loaded from scenarios
     */
    public headCollisionTestScenario(scenarioName: string = '90DegreePlaneCollision'): void {
        let checkedScenarios = new SimulationScenarios(scenarios);
        let scenario = checkedScenarios.getScenario(scenarioName);

        scenario.flights.forEach(
            (flight): Promise<void> => this.blueSkyDataProvider.createFlight(flight)
        );
    }
}