import { EventEmitter } from 'events';
import { RuntimeEventType, RuntimeEvent } from '../types/events.js';

class RuntimeEventBus extends EventEmitter {
  constructor() {
    super();
    // Allow more listeners since many processes might hook into the event bus
    this.setMaxListeners(100);
  }

  public emitEvent(type: RuntimeEventType, payload: any = {}): void {
    const event: RuntimeEvent = {
      type,
      payload,
      timestamp: Date.now(),
    };
    
    // Emit to internal listeners
    this.emit(type, event);
    
    // Emit a catch-all event for telemetry/websocket
    this.emit('*', event);
  }

  public onEvent(type: RuntimeEventType | '*', listener: (event: RuntimeEvent) => void): void {
    this.on(type, listener);
  }

  public offEvent(type: RuntimeEventType | '*', listener: (event: RuntimeEvent) => void): void {
    this.off(type, listener);
  }
}

export const eventBus = new RuntimeEventBus();
