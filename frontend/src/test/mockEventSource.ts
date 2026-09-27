import { vi } from "vitest";

type Listener = (event: MessageEvent<string>) => void;

/** Stands in for the browser EventSource in tests. */
export class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static instances: MockEventSource[] = [];

  readyState = MockEventSource.CONNECTING;
  onerror: ((event: Event) => void) | null = null;
  private listeners = new Map<string, Listener[]>();

  constructor(public url: string) {
    MockEventSource.instances.push(this);
  }

  static install() {
    MockEventSource.instances = [];
    vi.stubGlobal("EventSource", MockEventSource);
  }

  static last(): MockEventSource {
    const source = MockEventSource.instances.at(-1);
    if (!source) throw new Error("no EventSource was opened");
    return source;
  }

  addEventListener(type: string, listener: Listener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close() {
    this.readyState = MockEventSource.CLOSED;
  }

  emit(type: string, data: unknown) {
    const payload = typeof data === "string" ? data : JSON.stringify(data);
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data: payload }));
    }
  }

  fail(readyState: number) {
    this.readyState = readyState;
    this.onerror?.(new Event("error"));
  }
}
