/**
 * Configuration for a selection modal (scenarios or data sources).
 */
export interface SelectionModalConfig {
  title: string;
  options: { id: string; label: string }[];
  activeId?: string;
  variant: 'scenario' | 'dataSource';
  overlayId: string;
  extraButton?: { label: string; callback: () => void };
  onSelect: (id: string) => void;
}

/**
 * Generic modal that displays a list of options (e.g. scenarios or data sources)
 * and allows the user to select one. Supports scenario variant (teal buttons + optional
 * stop button) and dataSource variant (blue/green with active state).
 */
export class SelectionModal {
  private config: SelectionModalConfig;
  private readonly modalOverlay: HTMLDivElement;
  private readonly modalContent: HTMLDivElement;
  private readonly buttonsContainer: HTMLDivElement;
  private readonly headerElement: HTMLHeadingElement;
  private currentActiveId: string | undefined;

  constructor(config: SelectionModalConfig) {
    this.config = config;
    this.currentActiveId = config.activeId;
    this.modalOverlay = this.createModalOverlay(config.overlayId);
    this.modalContent = this.createModalContent();
    this.buttonsContainer = document.createElement('div');
    this.buttonsContainer.className = 'scenario-modal-buttons';
    this.headerElement = document.createElement('h2');
    this.buildModal();
  }

  private createModalOverlay(overlayId: string): HTMLDivElement {
    const overlay = document.createElement('div');
    overlay.id = overlayId;
    overlay.className = 'scenario-modal-overlay';
    overlay.addEventListener('click', (e: MouseEvent): void => {
      if (e.target === overlay) {
        this.hide();
      }
    });
    return overlay;
  }

  private createModalContent(): HTMLDivElement {
    const content = document.createElement('div');
    content.className = 'scenario-modal-content';
    return content;
  }

  private buildModal(): void {
    this.headerElement.className = 'scenario-modal-header';
    this.headerElement.textContent = this.config.title;
    this.modalContent.appendChild(this.headerElement);

    this.config.options.forEach((option): void => {
      const button = this.createOptionButton(option.id, option.label);
      this.buttonsContainer.appendChild(button);
    });

    if (this.config.extraButton) {
      const stopButton = this.createExtraButton(
        this.config.extraButton.label,
        this.config.extraButton.callback,
      );
      this.buttonsContainer.appendChild(stopButton);
    }

    this.modalContent.appendChild(this.buttonsContainer);
    this.modalOverlay.appendChild(this.modalContent);
    document.body.appendChild(this.modalOverlay);
  }

  private createOptionButton(optionId: string, label: string): HTMLButtonElement {
    const button = document.createElement('button');
    button.setAttribute('data-option-id', optionId);

    if (this.config.variant === 'scenario') {
      button.className = 'scenario-modal-button scenario-button';
    } else {
      button.className = 'scenario-modal-button data-source-option';
      if (optionId === this.currentActiveId) {
        button.classList.add('active');
      }
    }

    button.textContent = label;
    button.addEventListener('click', (): void => {
      this.handleOptionClick(optionId);
    });
    return button;
  }

  private createExtraButton(
    label: string,
    callback: () => void,
  ): HTMLButtonElement {
    const button = document.createElement('button');
    button.className = 'scenario-modal-button stop-button';
    button.textContent = label;
    button.addEventListener('click', (): void => {
      callback();
      this.hide();
    });
    return button;
  }

  private handleOptionClick(optionId: string): void {
    this.config.onSelect(optionId);

    if (this.config.variant === 'scenario') {
      this.hide();
      return;
    }

    this.currentActiveId = optionId;
    const options = this.buttonsContainer.querySelectorAll(
      '.data-source-option',
    ) as NodeListOf<HTMLButtonElement>;
    options.forEach((btn): void => {
      const id = btn.getAttribute('data-option-id');
      if (id === optionId) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
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
   * Rebuilds scenario/data-source option buttons.
   *
   * @param options New option ids and labels.
   * @param title Optional modal title.
   */
  public setOptions(
    options: { id: string; label: string }[],
    title?: string,
  ): void {
    this.config.options = options;
    if (title !== undefined) {
      this.config.title = title;
      this.headerElement.textContent = title;
    }

    while (this.buttonsContainer.firstChild) {
      this.buttonsContainer.removeChild(this.buttonsContainer.firstChild);
    }

    // Rebuild option buttons
    options.forEach((option): void => {
      this.buttonsContainer.appendChild(
        this.createOptionButton(option.id, option.label),
      );
    });
    
    if (this.config.extraButton) {
      this.buttonsContainer.appendChild(
        this.createExtraButton(
          this.config.extraButton.label,
          this.config.extraButton.callback,
        ),
      );
    }
  }
}
