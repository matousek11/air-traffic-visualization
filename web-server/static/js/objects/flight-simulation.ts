import type {Flight, Position} from "../types/flight";

export type FlightFromAPI = {
    flight_id: string;
    plane_type: string;
    lat: number;
    lon: number;
    heading: number;
    flight_level: number;
    speed: number;
    flight_plan: Array<{ name: string; flight_level: number; speed: number }>;
};

export class FlightSimulation {
    static readonly BASE_URL = 'http://localhost:8001';
    private flights: Flight[] = [];

    public async updateFlights() {
        try {
            const response = await fetch(FlightSimulation.BASE_URL + '/flights');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const apiFlights: FlightFromAPI[] = await response.json();
            this.flights = [];

            apiFlights.forEach(apiFlight => {
                const convertedFlight = this.convertApiFlightToFlight(apiFlight);
                this.flights.push(convertedFlight);
            });

            // Remove flights that are no longer in the API response
            const apiFlightIds = new Set(apiFlights.map(f => f.flight_id));
            this.flights = this.flights.filter(f => apiFlightIds.has(f.flightID));

            // Display all flights
            return this.flights;
        } catch (error) {
            console.error('Error updating flights:', error);
            return this.flights;
        }
    }

    public async resetSimulation() {
        try {
            const response = await fetch(FlightSimulation.BASE_URL + '/reset-simulation', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'}
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            // Clear the flights array
            this.flights = [];
        } catch (error) {
            console.error('Error resetting simulation:', error);
        }
    }

    private async createFlight(flight: Flight) {
        try {
            const response = await fetch(FlightSimulation.BASE_URL + '/flights', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    flight_id: flight.flightID,
                    plane_type: flight.planeType,
                    lat: flight.planePosition.position[0],
                    lon: flight.planePosition.position[1],
                    heading: flight.planePosition.heading,
                    flight_level: flight.planePosition.height,
                    speed: flight.planePosition.speed
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Response:', data);
        } catch (error) {
            console.error('Error making request:', error);
        }
    }

    async headCollisionTestScenario(): Promise<void> {
        let flight1: Flight = {
            flightID: "CSA202",
            planeType: "A320",
            planePosition: {
                speed: 250,
                heading: 90,
                height: 100,
                position: [50, 13.9]
            },
            flightPositions: []
        }

        let flight2: Flight = {
            flightID: "EZY451",
            planeType: "A320",
            planePosition: {
                speed: 250,
                heading: 0,
                height: 100,
                position: [49.935, 14.0]
            },
            flightPositions: []
        }

        await this.createFlight(flight1);
        await this.createFlight(flight2);
    }

    // Convert API flight to our Flight structure
    convertApiFlightToFlight = (apiFlight: FlightFromAPI): Flight => {
        // Convert flight_level (in feet) to height
        const height = apiFlight.flight_level;

        // Build flight positions from current position and heading
        // For simplicity, create a route showing current position and direction
        const currentPos: Position = [apiFlight.lat, apiFlight.lon];

        return {
            flightID: apiFlight.flight_id,
            planeType: apiFlight.plane_type,
            planePosition: {
                speed: apiFlight.speed,
                heading: apiFlight.heading,
                height: height,
                position: currentPos
            },
            flightPositions: [currentPos]
        };
    }
}