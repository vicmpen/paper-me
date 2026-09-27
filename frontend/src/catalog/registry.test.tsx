import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StaticSources } from "../paper/sources";
import { FIXTURES, OIL_SOURCES, toSpec } from "../styleguide/fixtures";
import { EditionView } from "./EditionView";

const fixture = (id: string) => FIXTURES.find((f) => f.id === id)!;

function renderFixture(id: string) {
  const f = fixture(id);
  return render(<StaticSources sources={f.sources}><EditionView spec={toSpec(f.lines)} /></StaticSources>);
}

describe("catalog components", () => {
  it("labels the main story with its outlet count", () => {
    renderFixture("full");
    expect(screen.getByText("Main story")).toBeInTheDocument();
    expect(screen.getByText(/Reported by 3 outlets/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Brent swings \$18/ })).toBeInTheDocument();
  });

  it("links cites to the source URL safely", () => {
    renderFixture("full");
    const link = screen.getAllByRole("link", { name: /Source 1: reuters.com/ })[0];
    expect(link).toHaveAttribute("href", OIL_SOURCES[0].url);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("marks stories citing a source seen before as updates", () => {
    renderFixture("full");
    expect(screen.getAllByText("Update").length).toBeGreaterThan(0);
  });

  it("has no main story label without a LeadStory", () => {
    renderFixture("no-lead");
    expect(screen.queryByText("Main story")).toBeNull();
  });

  it("numbers controls in reading order", () => {
    const { container } = renderFixture("no-lead");
    const numbers = [...container.querySelectorAll("svg text")].map((t) => t.textContent);
    expect(numbers).toEqual(["1", "2", "3"]);
  });

  it("renders a page whose children haven't all arrived", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    renderFixture("streaming");
    expect(screen.getByText("Main story")).toBeInTheDocument();
    warn.mockRestore();
  });

  it("renders model text as text, never HTML", () => {
    const lines = [
      '{"op":"add","path":"/root","value":"page"}',
      '{"op":"add","path":"/elements/page","value":{"type":"Page","props":{},"children":["s1"]}}',
      '{"op":"add","path":"/elements/s1","value":{"type":"Story","props":{"headline":"<b>bold</b>","dek":"<img src=x onerror=alert(1)>","cites":[1],"weight":"minor"},"children":[]}}',
    ];
    const { container } = render(<StaticSources sources={OIL_SOURCES}><EditionView spec={toSpec(lines)} /></StaticSources>);
    expect(screen.getByText("<b>bold</b>")).toBeInTheDocument();
    expect(container.querySelector("b, img")).toBeNull();
  });

  it("renders nothing for an empty spec", () => {
    const { container } = render(<EditionView spec={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing while only the root has streamed in", () => {
    const { container } = render(<EditionView spec={toSpec(['{"op":"add","path":"/root","value":"page"}'])} />);
    expect(container).toBeEmptyDOMElement();
  });
});
