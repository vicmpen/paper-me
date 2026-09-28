import { act, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FIXTURES } from "./fixtures";
import { Styleguide } from "./Styleguide";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("stream replay", () => {
  it("loops: the edition comes back after the reset gap", () => {
    vi.useFakeTimers();
    vi.stubGlobal("matchMedia", () => ({ matches: false }));
    vi.spyOn(console, "warn").mockImplementation(() => {}); // json-render: children not arrived yet
    render(<Styleguide />);
    const replay = within(screen.getByRole("region", { name: "Going to press (replay)" }));
    const lines = FIXTURES[0].lines.length;
    const tick = (n: number) => act(() => vi.advanceTimersByTime(700 * n));

    expect(replay.queryByText("Main story")).toBeNull();
    tick(lines);
    expect(replay.getByText("Main story")).toBeInTheDocument();
    tick(5); // four ticks holding the finished edition, then the reset
    expect(replay.queryByText("Main story")).toBeNull();
    tick(3); // root, page, lead
    expect(replay.getByText("Main story")).toBeInTheDocument();
  });
});
