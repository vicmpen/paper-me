import { afterEach, describe, expect, it, vi } from "vitest";
import { NotFoundError, fetchPaper, goToPress, openEditionStream } from "./api";
import { MockEventSource } from "./test/mockEventSource";

afterEach(() => vi.unstubAllGlobals());

describe("api", () => {
  it("goToPress POSTs to the relative API URL and returns the run id", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ run_id: 42 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(goToPress(3)).resolves.toBe(42);
    expect(fetchMock).toHaveBeenCalledWith("/api/agents/3/run", { method: "POST" });
  });

  it("maps 404 to NotFoundError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 404 })));
    await expect(fetchPaper(9)).rejects.toBeInstanceOf(NotFoundError);
  });

  it("opens the edition stream on a relative URL", () => {
    MockEventSource.install();
    openEditionStream(10);
    expect(MockEventSource.last().url).toBe("/api/runs/10/edition/stream");
  });
});
