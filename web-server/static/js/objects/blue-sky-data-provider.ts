import type {Flight, Position} from "../types/flight";

export type ApiFlightStructure = {
    flight_id: string;
    plane_type: string;
    lat: number;
    lon: number;
    heading: number;
    flight_level: number;
    speed: number;
    vertical_speed: number;
    flight_plan: Array<{ name: string; flight_level: number; speed: number }>;
};

/**
 * Represents data communication between js client and BlueSky simulation backend
 */
export class BlueSkyDataProvider {
    static readonly BASE_URL = 'http://localhost:8001';

    /**
     * Adds new flight into the simulation
     * @param flight
     */
    public async createFlight(flight: Flight): Promise<void> {
        try {
            const response = await fetch(BlueSkyDataProvider.BASE_URL + '/flights', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    flight_id: flight.flightID,
                    plane_type: flight.planeType,
                    lat: flight.planePosition.position[0],
                    lon: flight.planePosition.position[1],
                    heading: flight.planePosition.heading,
                    flight_level: flight.planePosition.height,
                    speed: flight.planePosition.speed,
                    vertical_speed: flight.planePosition.vertical_speed
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('create flight response:', data);
        } catch (error) {
            console.error('Error making request:', error);
        }
    }

    /**
     * Get updated data about all flights
     */
    public async updateFlights(): Promise<Flight[]> {
        try {
            const response = await fetch(BlueSkyDataProvider.BASE_URL + '/flights');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const apiFlights: ApiFlightStructure[] = await response.json();
            return apiFlights.map(apiFlight => this.mapApiFlightToFlight(apiFlight));
        } catch (error) {
            console.error('Error updating flights:', error);
            throw error;
        }
    }

    /**
     * Stops simulation and removes all flights from simulation
     */
    public async resetSimulation(): Promise<void> {
        try {
            const response = await fetch(BlueSkyDataProvider.BASE_URL + '/reset-simulation', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
        } catch (error) {
            console.error('Error resetting simulation:', error);
            throw error;
        }
    }

    /**
     * Converts Flight structure from API response to JS client Flight
     *
     * @param apiFlight Data to be converted into JS structure
     */
    private mapApiFlightToFlight (apiFlight: ApiFlightStructure): Flight {
        const currentPos: Position = [apiFlight.lat, apiFlight.lon];

        return {
            flightID: apiFlight.flight_id,
            planeType: apiFlight.plane_type,
            planePosition: {
                speed: apiFlight.speed,
                vertical_speed: apiFlight.vertical_speed,
                heading: apiFlight.heading,
                height: apiFlight.flight_level,
                position: currentPos
            },
            flightPositions: [currentPos]
        };
    }
}