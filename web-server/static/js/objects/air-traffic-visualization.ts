import {MapUi} from "./map-ui";

/**
 * Entry class for client web application.
 */
export class AirTrafficVisualization {
    private readonly mapUi: MapUi;

    /**
     * Automatically initialize web UI
     */
    constructor() {
        this.mapUi = new MapUi();
        this.initHandlers();
    }

    /**
     * Prepare event listeners for UI actions
     */
    private initHandlers (): void {
        const uiHandlers: Record<string, () => void> = {
            'bottom-left-button': () => this.startScenario(),
        };

        Object.entries(uiHandlers).forEach(([elementId, handler]): void => {
            this.bindButton(elementId, handler);
        });
    }

    /**
     * Bind handler to click event on element
     *
     * @param elementId
     * @param handler
     *
     * @throws Error When HTML element with buttonID doesn't exist
     */
    private bindButton(elementId: string, handler: () => void): void {
        const button: HTMLElement|null = document.getElementById(elementId);
        if (button === null) {
            throw Error(`Button with ID ${elementId} doesn't exist in HTML.`);
        }

        button.addEventListener('click', handler);
    }

    /**
     * Starts selected simulation scenario
     */
    private startScenario(): void {
        this.mapUi.startHeadOnScenario();
    }
}