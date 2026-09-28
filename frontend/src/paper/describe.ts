import type { Spec, UIElement } from "@json-render/core";
import type { EditionSummary, Source } from "../api";
import { outletsOf } from "../lib/outlets";

export const STAGES = [
  { id: "planning", label: "Planning coverage" },
  { id: "searching", label: "Searching" },
  { id: "writing", label: "Writing" },
  { id: "composing", label: "Laying out the page" },
] as const;

export const KIND_LABEL: Record<string, string> = {
  LeadStory: "Main story", Story: "Story", Briefs: "In brief", Split: "Two sides",
  Figures: "Key figures", Timeline: "Timeline", Analysis: "What it means",
};

export type Freshness = "new" | "update" | "continuing" | null;

export interface ControlRow {
  number: number; id: string; kind: string; label: string;
  outlets: number; readSeconds: number; freshness: Freshness;
}

function collect(value: unknown, cites: Set<number>, words: string[]) {
  if (Array.isArray(value)) value.forEach((v) => collect(v, cites, words));
  else if (value && typeof value === "object") {
    for (const [key, inner] of Object.entries(value)) {
      if (key === "cites" && Array.isArray(inner)) inner.forEach((n) => typeof n === "number" && cites.add(n));
      else collect(inner, cites, words);
    }
  } else if (typeof value === "string") words.push(...value.split(/\s+/).filter(Boolean));
}

function labelOf(element: UIElement): string {
  const props = element.props as Record<string, unknown>;
  const text = props.headline ?? props.title ?? props.heading;
  return typeof text === "string" ? text : KIND_LABEL[element.type] ?? element.type;
}

function freshness(cites: number[], sources: Source[]): Freshness {
  const cited = sources.filter((s) => cites.includes(s.n));
  if (cited.length === 0) return null;
  const seen = cited.filter((s) => s.seen_before).length;
  return seen === 0 ? "new" : seen === cited.length ? "continuing" : "update";
}

/** One row per arrived block, numbered in reading order like Page numbers its controls. */
export function controlRows(spec: Spec | null, sources: Source[]): ControlRow[] {
  // The first streamed line sets only the root, so elements may be missing.
  const page = spec?.root ? spec.elements?.[spec.root] : undefined;
  if (!spec || !page) return [];
  const rows: ControlRow[] = [];
  for (const id of page.children ?? []) {
    const element = spec.elements[id];
    if (!element) continue;
    const cites = new Set<number>();
    const words: string[] = [];
    collect(element.props, cites, words);
    rows.push({
      number: rows.length + 1, id, kind: element.type, label: labelOf(element),
      outlets: outletsOf([...cites], sources).size,
      readSeconds: Math.round((words.length / 200) * 60),
      freshness: freshness([...cites], sources),
    });
  }
  return rows;
}

export function hasNoLead(spec: Spec | null): boolean {
  const page = spec?.root ? spec.elements?.[spec.root] : undefined;
  const first = page?.children?.[0];
  const element = first ? spec!.elements[first] : undefined;
  return !!element && element.type !== "LeadStory";
}

export function formatRead(seconds: number): string {
  return seconds < 45 ? "<1 min" : `${Math.max(1, Math.round(seconds / 60))} min`;
}

/** Editions are newest first; the oldest is Edition 1. */
export function editionNumber(editions: Pick<EditionSummary, "run_id">[], runId: number | null): number | null {
  const index = editions.findIndex((e) => e.run_id === runId);
  return index < 0 ? null : editions.length - index;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}
