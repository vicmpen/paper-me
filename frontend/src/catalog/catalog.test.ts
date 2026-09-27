// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { catalog } from "./catalog";
import { buildPrompt, componentSchemas } from "./prompt";

const dir = new URL("../../../webapp/catalog/", import.meta.url);

describe("catalog export", () => {
  it("committed prompt matches the catalog (run npm run export-catalog)", () => {
    expect(readFileSync(new URL("catalog.prompt.txt", dir), "utf8")).toBe(buildPrompt());
  });

  it("committed schemas match the catalog (run npm run export-catalog)", () => {
    const committed = JSON.parse(readFileSync(new URL("catalog.schema.json", dir), "utf8"));
    expect(committed).toEqual(componentSchemas());
  });

  it("has exactly the eight paper components", () => {
    expect(Object.keys(catalog.data.components).sort()).toEqual(
      ["Analysis", "Briefs", "Figures", "LeadStory", "Page", "Split", "Story", "Timeline"],
    );
  });

  it("every component schema forbids extra props", () => {
    for (const [name, schema] of Object.entries(componentSchemas())) {
      expect((schema as { additionalProperties?: boolean }).additionalProperties, name).toBe(false);
    }
  });

  it("the prompt never invites dynamic props, actions or invented content", () => {
    const prompt = buildPrompt();
    for (const banned of ["$state", "$item", "$bindState", "visible", "repeat", "sample data", "realistic"]) {
      expect(prompt).not.toContain(banned);
    }
    expect(prompt).toContain('{"op":"add","path":"/root","value":"page"}');
  });
});
