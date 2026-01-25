import { z } from 'zod';

const PositionSchema = z.tuple([z.number(), z.number()]);

const PlanePositionSchema = z.object({
  speed: z.number().nonnegative(),
  vertical_speed: z.number(),
  heading: z.number().nonnegative(),
  target_flight_level: z.number().nonnegative().nullable().optional().default(null),
  height: z.number().nonnegative(),
  position: PositionSchema,
});

const FlightSchema = z.object({
  flightID: z.string().min(1),
  planeType: z.string().min(1),
  planePosition: PlanePositionSchema,
  flightPositions: z.array(PositionSchema),
});

const SimulationScenarioSchema = z.object({
  name: z.string().min(1),
  flights: z.array(FlightSchema).min(1),
});

const SimulationScenariosDataSchema = z
  .record(z.string(), SimulationScenarioSchema)
  .refine((data) => Object.keys(data).length > 0, {
    message: 'Simulation scenarios must contain at least one scenario',
  });

type SimulationScenario = z.infer<typeof SimulationScenarioSchema>;
type SimulationScenariosData = z.infer<typeof SimulationScenariosDataSchema>;

/**
 * Class representing simulation scenarios json with validation using Zod
 */
export class SimulationScenarios {
  private readonly scenarios: SimulationScenariosData;

  /**
   * Creates a new SimulationScenarios instance with validation
   *
   * @param data JSON data to validate and store
   * @throws Error if validation fails
   */
  constructor(data: unknown) {
    this.scenarios = SimulationScenariosDataSchema.parse(data);
  }

  /**
   * Gets a scenario by name
   *
   * @param scenarioName Name of the scenario to retrieve
   * @throws Error scenario doesn't exist
   */
  public getScenario(scenarioName: string): SimulationScenario {
    if (!(scenarioName in this.scenarios)) {
      throw new Error(`Scenario "${scenarioName}" not found.`);
    }

    return this.scenarios[scenarioName] as SimulationScenario;
  }

  /**
   * Gets all scenario names
   */
  public getScenarioNames(): string[] {
    return Object.keys(this.scenarios);
  }

  /**
   * Gets all scenarios
   */
  public getAllScenarios(): SimulationScenariosData {
    return this.scenarios;
  }
}
