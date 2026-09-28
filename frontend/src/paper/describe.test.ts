import type { Spec } from "@json-render/core";
import { describe, expect, it } from "vitest";
import { FIXTURES, OIL_SOURCES, toSpec } from "../styleguide/fixtures";
import { controlRows, editionNumber, formatRead, hasNoLead } from "./describe";

const spec = (id: string) => toSpec(FIXTURES.find((f) => f.id === id)!.lines);

describe("describe", () => {
  it("lists controls in reading order with coverage and freshness", () => {
    const rows = controlRows(spec("full"), OIL_SOURCES);
    expect(rows.map((r) => r.number)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    expect(rows[0]).toMatchObject({ kind: "LeadStory", label: expect.stringMatching(/^Brent swings/), outlets: 3, freshness: "new" });
    expect(rows.find((r) => r.id === "s2")!.freshness).toBe("continuing");
  });

  it("numbers only the controls that have arrived", () => {
    expect(controlRows(spec("streaming"), OIL_SOURCES).map((r) => r.number)).toEqual([1]);
  });

  it("copes with the first streamed line, which sets only the root", () => {
    const rootOnly = { root: "page" } as unknown as Spec;
    expect(controlRows(rootOnly, OIL_SOURCES)).toEqual([]);
    expect(hasNoLead(rootOnly)).toBe(false);
  });

  it("knows when an edition has no main story", () => {
    expect(hasNoLead(spec("no-lead"))).toBe(true);
    expect(hasNoLead(spec("full"))).toBe(false);
    expect(hasNoLead(null)).toBe(false);
  });

  it("formats reading time and edition numbers", () => {
    expect(formatRead(20)).toBe("<1 min");
    expect(formatRead(150)).toBe("3 min");
    const editions = [{ run_id: 12 }, { run_id: 11 }, { run_id: 10 }] as never[];
    expect(editionNumber(editions, 12)).toBe(3);
    expect(editionNumber(editions, 10)).toBe(1);
    expect(editionNumber(editions, 99)).toBeNull();
  });
});
