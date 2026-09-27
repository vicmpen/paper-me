import type { Source } from "../api";

/** Same rule as webapp/edition_spec.py outlet(): lower-case hostname without a leading "www.". */
export function outlet(url: string): string {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return "";
  }
}

export function outletsOf(cites: number[], sources: Source[]): Set<string> {
  const byNumber = new Map(sources.map((s) => [s.n, s]));
  const outlets = new Set<string>();
  for (const n of cites) {
    const source = byNumber.get(n);
    const name = source ? outlet(source.url) : "";
    if (name) outlets.add(name);
  }
  return outlets;
}
