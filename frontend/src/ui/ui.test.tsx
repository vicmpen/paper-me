import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ControlCircle, MAX_RINGS } from "./ControlCircle";
import { contourPaths } from "./ContourField";
import { LEGEND } from "./inks";
import { Legend } from "./Legend";

describe("map primitives", () => {
  it("draws one contour ring per outlet, capped", () => {
    const { container, rerender } = render(<ControlCircle number={1} rings={3} />);
    expect(container.querySelectorAll("[data-ring]")).toHaveLength(3);
    rerender(<ControlCircle number={1} rings={20} />);
    expect(container.querySelectorAll("[data-ring]")).toHaveLength(MAX_RINGS);
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(container.querySelector("text")).toHaveTextContent("1");
  });

  it("contour fields are deterministic per seed", () => {
    expect(contourPaths(3)).toEqual(contourPaths(3));
    expect(contourPaths(3)).not.toEqual(contourPaths(4));
    expect(contourPaths(3).every((d) => d.startsWith("M") && d.endsWith("Z"))).toBe(true);
  });

  it("each legend ink has exactly one meaning", () => {
    const tokens = LEGEND.map((entry) => entry.token);
    expect(new Set(tokens).size).toBe(tokens.length);
    const { getByText } = render(<Legend />);
    expect(getByText(/one per independent outlet/)).toBeInTheDocument();
  });
});
