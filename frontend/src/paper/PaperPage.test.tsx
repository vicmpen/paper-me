import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Paper } from "../api";
import { FIXTURES, OIL_SOURCES } from "../styleguide/fixtures";
import { MockEventSource } from "../test/mockEventSource";
import { PaperPage } from "./PaperPage";

const edition = (run_id: number, over: object = {}) => ({
  run_id, started_at: "2026-09-27T07:00:00+00:00", finished_at: "2026-09-27T07:01:00+00:00",
  status: "succeeded", edition: "composed", error: null, answer: "An answer.", ...over,
});

function mockApi(paper: Paper | null, extra: Record<string, unknown> = {}) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url}`;
    const routes: Record<string, unknown> = {
      "GET /api/agents/3/paper": paper,
      [`GET /api/runs/${paper?.current_run_id}/sources`]: OIL_SOURCES,
      ...extra,
    };
    const body = routes[key];
    if (body == null) return new Response("", { status: 404 });
    return new Response(JSON.stringify(body), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path=":agentId" element={<PaperPage />} />
        <Route path=":agentId/:runId" element={<PaperPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function stream(lines: string[], done: object | null = { status: "succeeded", edition: "composed", error: null }) {
  const source = MockEventSource.last();
  act(() => {
    source.emit("status", { status: "succeeded", stage: null });
    source.emit("reset", {});
    for (const line of lines) source.emit("patch", line);
    if (done) source.emit("done", done);
  });
}

const PAPER: Paper = {
  agent: { id: 3, name: "Oil desk", query: "oil prices" },
  current_run_id: 12,
  editions: [edition(12), edition(11, { status: "failed", edition: null, error: "search provider failed" }), edition(10)] as Paper["editions"],
};

beforeEach(() => MockEventSource.install());
afterEach(() => vi.unstubAllGlobals());

describe("PaperPage", () => {
  it("shows the masthead, the streamed edition and its control table", async () => {
    mockApi(PAPER);
    renderAt("/3");
    expect(await screen.findByRole("heading", { level: 1, name: "Oil desk" })).toBeInTheDocument();
    expect(screen.getByText(/^Edition 3 ·/)).toBeInTheDocument();   // masthead, not the rail link
    stream(FIXTURES[0].lines);
    expect(within(screen.getByRole("main")).getByText("Main story")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Control descriptions" });
    expect(table.querySelectorAll("tbody tr")).toHaveLength(8);
  });

  it("notes when no story dominates", async () => {
    mockApi(PAPER);
    renderAt("/3");
    await screen.findByRole("heading", { level: 1 });
    stream(FIXTURES.find((f) => f.id === "no-lead")!.lines);
    expect(screen.getByText("No single story dominates this edition.")).toBeInTheDocument();
  });

  it("lists back issues, including runs that didn't go to press", async () => {
    mockApi(PAPER);
    renderAt("/3");
    const rail = await screen.findByRole("navigation", { name: "Back issues" });
    expect(rail).toHaveTextContent("Didn't go to press");
    expect(screen.getByRole("link", { name: /Edition 1/ })).toHaveAttribute("href", "/3/10");
  });

  it("warns when the latest run failed", async () => {
    mockApi({ ...PAPER, current_run_id: 10, editions: [edition(11, { status: "failed", edition: null, error: "search provider failed" }), edition(10)] as Paper["editions"] });
    renderAt("/3");
    expect(await screen.findByText("Latest run didn't go to press: search provider failed")).toBeInTheDocument();
  });

  it("goes to press", async () => {
    const fetchMock = mockApi(PAPER, { "POST /api/agents/3/run": { run_id: 13 } });
    renderAt("/3");
    fireEvent.click(await screen.findByRole("button", { name: "Go to press" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/agents/3/run", { method: "POST" }));
  });

  it("follows the new run after going to press, sources included", async () => {
    const pressed: Paper = { ...PAPER, current_run_id: 13, editions: [edition(13, { status: "running", edition: null, finished_at: null }), ...PAPER.editions] as Paper["editions"] };
    let paper = PAPER;
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const key = `${init?.method ?? "GET"} ${url}`;
      if (key === "POST /api/agents/3/run") {
        paper = pressed;
        return new Response(JSON.stringify({ run_id: 13 }), { status: 200 });
      }
      if (key === "GET /api/agents/3/paper") return new Response(JSON.stringify(paper), { status: 200 });
      if (key.endsWith("/sources")) return new Response(JSON.stringify(OIL_SOURCES), { status: 200 });
      return new Response("", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);
    renderAt("/3");
    fireEvent.click(await screen.findByRole("button", { name: "Go to press" }));
    expect(await screen.findByRole("button", { name: "Going to press…" })).toBeDisabled();
    await waitFor(() => expect(MockEventSource.last().url).toBe("/api/runs/13/edition/stream"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/runs/13/sources"));
    act(() => MockEventSource.last().emit("status", { status: "running", stage: "searching" }));
    const legs = screen.getByRole("list", { name: "Going to press" });
    expect(within(legs).getByText("Searching")).toHaveAttribute("aria-current", "step");
  });

  it("says in words whether each control is new or continuing", async () => {
    mockApi(PAPER);
    renderAt("/3");
    await screen.findByRole("heading", { level: 1 });
    stream(FIXTURES[0].lines);
    const rows = () => within(screen.getByRole("table", { name: "Control descriptions" })).getAllByRole("row").slice(1);
    await waitFor(() => expect(rows()[0]).toHaveTextContent(/New$/)); // once the sources have loaded
    expect(rows()[2]).toHaveTextContent(/Continuing$/);
  });

  it("disables the press while a run is going", async () => {
    mockApi({ ...PAPER, current_run_id: 13, editions: [edition(13, { status: "running", edition: null, finished_at: null }), ...PAPER.editions] as Paper["editions"] });
    renderAt("/3");
    expect(await screen.findByRole("button", { name: "Going to press…" })).toBeDisabled();
  });

  it("shows the answer for an empty edition", async () => {
    mockApi({ ...PAPER, editions: [edition(12, { edition: "empty", answer: "Nothing relevant this week." }), ...PAPER.editions.slice(1)] as Paper["editions"] });
    renderAt("/3");
    await screen.findByRole("heading", { level: 1 });
    stream([], { status: "succeeded", edition: "empty", error: null });
    expect(screen.getByText("Nothing relevant this week.")).toBeInTheDocument();
  });

  it("says a failed run didn't go to press, and a paper never printed has no edition yet", async () => {
    mockApi(PAPER);
    renderAt("/3/11");
    const main = within(await screen.findByRole("main"));
    expect(main.getByRole("heading", { name: "Didn't go to press" })).toBeInTheDocument();
    expect(main.getByText("search provider failed")).toBeInTheDocument();

    mockApi({ ...PAPER, current_run_id: null, editions: [edition(11, { status: "failed", edition: null, error: "search provider failed" })] as Paper["editions"] });
    renderAt("/3");
    expect(await screen.findByRole("heading", { name: "No edition yet" })).toBeInTheDocument();
    expect(screen.queryByText("No news was found in this window.")).toBeNull();
  });

  it("says when the paper doesn't exist", async () => {
    mockApi(null);
    renderAt("/3");
    expect(await screen.findByRole("heading", { name: "This paper doesn't exist" })).toBeInTheDocument();
  });
});
