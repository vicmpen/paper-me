import { createSpecStreamCompiler, type Spec } from "@json-render/core";
import type { Source } from "../api";

// Synthetic fixture editions: realistic shape, invented text. Labelled as
// fixtures in the styleguide; never shown as real news.

export interface Fixture { id: string; title: string; note: string; lines: string[]; sources: Source[] }

const src = (n: number, url: string, title: string, seen = false): Source => ({
  n, url, title, source: new URL(url).hostname, published: "2026-09-26", summary: "Fixture summary.", seen_before: seen,
});

export const OIL_SOURCES: Source[] = [
  src(1, "https://www.reuters.com/fixture/brent-106", "Brent tops $106 as Hormuz threat widens"),
  src(2, "https://apnews.com/fixture/oil-jumps", "Oil jumps after Houthi strike on Saudi site"),
  src(3, "https://www.bbc.co.uk/fixture/hormuz", "Hormuz standoff enters its seventh month"),
  src(4, "https://www.ft.com/fixture/pipeline", "Saudi East–West pipeline restarts after 11 days"),
  src(5, "https://www.bloomberg.com/fixture/diesel", "Diesel export-ban talk widens WTI discount", true),
  src(6, "https://www.cnbc.com/fixture/opec", "OPEC+ pauses output hikes through October"),
  src(7, "https://www.aljazeera.com/fixture/ceasefire", "Two-night pause in strikes lifts ceasefire hopes"),
];

const root = JSON.stringify({ op: "add", path: "/root", value: "page" });
const add = (id: string, type: string, props: object, children: string[] = []) =>
  JSON.stringify({ op: "add", path: `/elements/${id}`, value: { type, props, children } });
const page = (children: string[], props: object = {}) => add("page", "Page", props, children);
const story = (id: string, headline: string, cites: number[], weight: "major" | "minor" = "minor") =>
  add(id, "Story", { headline, dek: "What happened, in one or two sentences drawn from the source.", cites, weight });

const FULL = [
  root,
  page(["lead", "s1", "s2", "split", "figs", "time", "brief", "what"], {
    bottomLine: { text: "Hormuz escalation kept Brent above $100 most of the week before a pause in strikes knocked it under $88.", cites: [1, 2, 7] },
  }),
  add("lead", "LeadStory", {
    kicker: "Energy",
    headline: "Brent swings $18 as the Hormuz standoff flares, then pauses",
    dek: "Threats to widen the war sent Brent above $106; two quiet nights sent it below $88.",
    body: [
      "Prices climbed early in the week after Iran threatened to take the conflict into the Indian Ocean and a Houthi strike hit a Saudi facility.",
      "A two-night pause in US–Iran strikes then raised hopes that the strait could reopen, and Brent fell more than 9% in a day.",
    ],
    cites: [1, 2, 3],
  }),
  story("s1", "Saudi East–West pipeline restarts after an 11-day outage", [4], "major"),
  story("s2", "Diesel export-ban talk widens the WTI discount to $12", [5]),
  add("split", "Split", {
    title: "What moved prices",
    sides: [
      { label: "Pushing up", direction: "up", points: [{ text: "Threats to widen the war", cites: [1] }, { text: "Strike on a Saudi facility", cites: [2] }] },
      { label: "Pushing down", direction: "down", points: [{ text: "Pause in US–Iran strikes", cites: [7] }, { text: "Pipeline flows resume", cites: [4] }] },
    ],
  }),
  add("figs", "Figures", {
    items: [
      { value: "$106", label: "Brent peak this week", cites: [1] },
      { value: "−9%", label: "One-day drop on the pause in strikes", cites: [7] },
      { value: "$12", label: "WTI discount to Brent", cites: [5] },
    ],
  }),
  add("time", "Timeline", {
    title: "How the week unfolded",
    events: [
      { date: "Sep 22", text: "Iran threatens to widen the war", cites: [1] },
      { date: "Sep 24", text: "Saudi pipeline restarts", cites: [4] },
      { date: "Sep 26", text: "Strikes pause for two nights", cites: [7] },
    ],
  }),
  add("brief", "Briefs", {
    title: "In brief",
    items: [
      { text: "OPEC+ pauses output hikes through October ahead of 2027 quota talks.", cites: [6] },
      { text: "The standoff enters its seventh month.", cites: [3] },
    ],
  }),
  add("what", "Analysis", {
    heading: "What it means",
    paragraphs: ["Supply risk, not supply itself, is setting the price: every sign of de-escalation takes several dollars out of Brent within a day."],
    cites: [1, 4, 7],
  }),
];

export const FIXTURES: Fixture[] = [
  { id: "full", title: "Full edition", note: "Main story earned by three outlets, and every block type.", lines: FULL, sources: OIL_SOURCES },
  {
    id: "no-lead", title: "No main story", note: "No story reported by more outlets than the others.",
    lines: [root, page(["s1", "s2", "s3"]), story("s1", "Pipeline restarts after an outage", [4], "major"),
      story("s2", "OPEC+ pauses output hikes", [6]), story("s3", "Standoff enters its seventh month", [3])],
    sources: OIL_SOURCES,
  },
  {
    id: "single", title: "Single source", note: "An edition built from one article.",
    lines: [root, page(["s1"]), story("s1", "Brent tops $106 as the Hormuz threat widens", [1], "major")],
    sources: OIL_SOURCES.slice(0, 1),
  },
  {
    id: "demoted", title: "Demoted lead", note: "Claude proposed a lead from one outlet; the server demoted it to a major story.",
    lines: [root, page(["lead", "s1"]), story("lead", "Brent tops $106 as the Hormuz threat widens", [1], "major"),
      story("s1", "Pipeline restarts", [4])],
    sources: OIL_SOURCES,
  },
  {
    id: "long", title: "Longest headlines and decks", note: "Text at the catalog limits.",
    lines: [root, page(["s1"]), add("s1", "Story", { kicker: "K".repeat(40), headline: "H".repeat(80) + " " + "h".repeat(79), dek: "D ".repeat(200).trim(), cites: [1, 2, 3, 4, 5, 6, 7], weight: "major" })],
    sources: OIL_SOURCES,
  },
  {
    id: "twelve", title: "Twelve elements", note: "The maximum page: Page plus eleven blocks.",
    lines: [root, page(Array.from({ length: 11 }, (_, i) => `s${i}`)),
      ...Array.from({ length: 11 }, (_, i) => story(`s${i}`, `Story number ${i + 1}`, [(i % 7) + 1], i < 2 ? "major" : "minor"))],
    sources: OIL_SOURCES,
  },
  {
    id: "bottom-line", title: "Bottom line without a main story", note: "A bottom line can stand alone.",
    lines: [root, page(["s1", "s2"], { bottomLine: { text: "Quiet week: no single development moved the market.", cites: [6] } }),
      story("s1", "OPEC+ pauses output hikes", [6]), story("s2", "Standoff enters its seventh month", [3])],
    sources: OIL_SOURCES,
  },
  {
    id: "fallback", title: "Rules-based edition",
    note: "What the paper shows when compose fails: the lead from the answer, one story per source, then briefs.",
    lines: [root, page(["lead", "s1", "s2", "s3", "briefs"], { bottomLine: { text: "Escalation pushed Brent above $106.", cites: [1, 2, 3] } }),
      add("lead", "LeadStory", { headline: "Brent tops $106 as Hormuz threat widens", dek: "Fixture summary.", body: ["Escalation pushed Brent above $106."], cites: [1, 2, 3] }),
      story("s1", "Saudi East–West pipeline restarts after 11 days", [4]),
      story("s2", "Diesel export-ban talk widens WTI discount", [5]),
      story("s3", "OPEC+ pauses output hikes through October", [6]),
      add("briefs", "Briefs", { title: "In brief", items: [{ text: "A two-night pause in strikes lifted ceasefire hopes.", cites: [7] }] })],
    sources: OIL_SOURCES,
  },
  {
    id: "streaming", title: "Mid-stream", note: "The page lists a child that hasn't arrived yet.",
    lines: [root, page(["lead", "s1"]), FULL[2]],
    sources: OIL_SOURCES,
  },
];

export function toSpec(lines: string[]): Spec {
  const compiler = createSpecStreamCompiler<Spec>();
  compiler.push(lines.join("\n") + "\n");
  return compiler.getResult();
}
