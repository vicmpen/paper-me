import { describe, expect, it } from "vitest";
import type { Source } from "../api";
import { outlet, outletsOf } from "./outlets";

const source = (n: number, url: string): Source => ({
  n, url, title: "t", source: "s", published: "", summary: "", seen_before: false,
});

describe("outlets", () => {
  it("outlet strips www and lowercases, like the Python outlet()", () => {
    expect(outlet("https://WWW.Reuters.com/x")).toBe("reuters.com");
    expect(outlet("https://reuters.com:443/y")).toBe("reuters.com");
    expect(outlet("not a url")).toBe("");
  });

  it("counts distinct outlets among cited sources", () => {
    const sources = [source(1, "https://www.reuters.com/a"), source(2, "https://reuters.com/b"),
      source(3, "https://apnews.com/c")];
    expect(outletsOf([1, 2], sources).size).toBe(1);
    expect(outletsOf([1, 2, 3, 9], sources)).toEqual(new Set(["reuters.com", "apnews.com"]));
  });
});
