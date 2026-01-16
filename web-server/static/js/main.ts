import {MapUi} from "./helpers/map-ui";

class AirTrafficVisualization {
    private mapUi: MapUi;

    constructor() {
        this.mapUi = new MapUi();
    }

    startApplication(): void {
        this.initHandlers();
    }

    initHandlers (): void {
        const bottomLeftButton = document.getElementById('bottom-left-button');
        if (bottomLeftButton) {
            bottomLeftButton.addEventListener('click', () => this.startScenario());
        }
    }

    startScenario(): void {
        this.mapUi.startHeadOnScenario();
    }
}

new AirTrafficVisualization().startApplication();