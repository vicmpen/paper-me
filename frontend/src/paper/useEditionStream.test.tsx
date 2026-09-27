import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockEventSource } from "../test/mockEventSource";
import { useEditionStream } from "./useEditionStream";

const ROOT = '{"op":"add","path":"/root","value":"page"}';
const PAGE = '{"op":"add","path":"/elements/page","value":{"type":"Page","props":{},"children":["s1"]}}';
const S1 = '{"op":"add","path":"/elements/s1","value":{"type":"Story","props":{"headline":"H","dek":"D","cites":[1],"weight":"minor"},"children":[]}}';

beforeEach(() => MockEventSource.install());
afterEach(() => vi.unstubAllGlobals());

function feed(...lines: string[]) {
  const source = MockEventSource.last();
  act(() => {
    source.emit("reset", {});
    for (const line of lines) source.emit("patch", line);
  });
}

describe("useEditionStream", () => {
  it("builds the spec from patch lines", () => {
    const { result } = renderHook(() => useEditionStream(10, 3));
    feed(ROOT, PAGE, S1);
    expect(result.current.spec?.root).toBe("page");
    expect(result.current.spec?.elements.s1.type).toBe("Story");
  });

  it("tracks status and stage", () => {
    const { result } = renderHook(() => useEditionStream(10, 3));
    act(() => MockEventSource.last().emit("status", { status: "running", stage: "composing" }));
    expect(result.current.status).toBe("running");
    expect(result.current.stage).toBe("composing");
  });

  it("reconnect replay does not duplicate", () => {
    const { result } = renderHook(() => useEditionStream(10, 3));
    feed(ROOT, PAGE, S1);
    feed(ROOT, PAGE, S1); // the server replays from the start after a reset
    expect(result.current.spec?.elements.page.children).toEqual(["s1"]);
    expect(Object.keys(result.current.spec?.elements ?? {})).toEqual(["page", "s1"]);
  });

  it("done closes the stream and records the edition", () => {
    const { result } = renderHook(() => useEditionStream(10, 3));
    act(() => MockEventSource.last().emit("done", { status: "succeeded", edition: "fallback", error: null }));
    expect(result.current.done).toBe(true);
    expect(result.current.edition).toBe("fallback");
    expect(MockEventSource.last().readyState).toBe(MockEventSource.CLOSED);
  });

  it("a closed stream for a run that no longer exists reports not found", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      agent: { id: 3, name: "Oil", query: "q" }, current_run_id: null, editions: [],
    }), { status: 200 })));
    const { result } = renderHook(() => useEditionStream(10, 3));
    act(() => MockEventSource.last().fail(MockEventSource.CLOSED));
    await waitFor(() => expect(result.current.notFound).toBe(true));
  });

  it("a paper fetch that settles after the run changed is ignored", async () => {
    let respond: (response: Response) => void = () => {};
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => { respond = resolve; })));
    const { result, rerender } = renderHook(({ runId }) => useEditionStream(runId, 3), {
      initialProps: { runId: 10 },
    });
    act(() => MockEventSource.last().fail(MockEventSource.CLOSED));
    rerender({ runId: 11 });
    await act(async () => respond(new Response(JSON.stringify({
      agent: { id: 3, name: "Oil", query: "q" }, current_run_id: 11, editions: [],
    }), { status: 200 })));
    expect(result.current.notFound).toBe(false);
    expect(result.current.done).toBe(false);
  });

  it("a reconnecting stream is left to the browser", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useEditionStream(10, 3));
    act(() => MockEventSource.last().fail(MockEventSource.CONNECTING));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.done).toBe(false);
  });

  it("opens nothing without a run", () => {
    renderHook(() => useEditionStream(null, 3));
    expect(MockEventSource.instances).toHaveLength(0);
  });
});
