// Every request the paper makes goes through this module, with relative
// /api URLs, so auth and 401 handling land in one file later.

export type RunStatus = "running" | "succeeded" | "failed";
export type EditionKind = "composed" | "fallback" | "empty" | null;

export interface EditionSummary {
  run_id: number;
  started_at: string;
  finished_at: string | null;
  status: RunStatus;
  edition: EditionKind;
  error: string | null;
  answer: string | null;
}

export interface Paper {
  agent: { id: number; name: string; query: string };
  current_run_id: number | null;
  editions: EditionSummary[];
}

export interface Source {
  n: number;
  title: string;
  url: string;
  source: string;
  published: string;
  summary: string;
  seen_before: boolean;
}

export class NotFoundError extends Error {}

async function readJson<T>(response: Response, url: string): Promise<T> {
  if (response.status === 404) throw new NotFoundError(url);
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return (await response.json()) as T;
}

export async function fetchPaper(agentId: number): Promise<Paper> {
  const url = `/api/agents/${agentId}/paper`;
  return readJson<Paper>(await fetch(url), url);
}

export async function fetchSources(runId: number): Promise<Source[]> {
  const url = `/api/runs/${runId}/sources`;
  return readJson<Source[]>(await fetch(url), url);
}

export async function goToPress(agentId: number): Promise<number> {
  const url = `/api/agents/${agentId}/run`;
  const body = await readJson<{ run_id: number }>(await fetch(url, { method: "POST" }), url);
  return body.run_id;
}

export function openEditionStream(runId: number): EventSource {
  return new EventSource(`/api/runs/${runId}/edition/stream`);
}
