import { useEffect, useState } from "react";
import { createSpecStreamCompiler, type Spec } from "@json-render/core";
import { fetchPaper, NotFoundError, openEditionStream, type EditionKind, type RunStatus } from "../api";

export interface EditionStreamState {
  spec: Spec | null;
  status: RunStatus | null;
  stage: string | null;
  edition: EditionKind;
  error: string | null;
  done: boolean;
  notFound: boolean;
}

const INITIAL: EditionStreamState = {
  spec: null, status: null, stage: null, edition: null, error: null, done: false, notFound: false,
};

/**
 * Follows a run's edition stream. The server replays the edition from the
 * start after every "reset" (including on reconnect), so the compiler is
 * cleared on reset and rebuilt from the patch lines that follow.
 */
export function useEditionStream(runId: number | null, agentId: number): EditionStreamState {
  const [state, setState] = useState<EditionStreamState>(INITIAL);

  useEffect(() => {
    setState(INITIAL);
    if (runId == null) return;
    const compiler = createSpecStreamCompiler<Spec>();
    const source = openEditionStream(runId);
    const publish = () => {
      const result = compiler.getResult();
      setState((s) => ({ ...s, spec: result.root ? { ...result } : null }));
    };

    source.addEventListener("reset", () => {
      compiler.reset();
      publish();
    });
    source.addEventListener("patch", (event) => {
      compiler.push((event as MessageEvent<string>).data + "\n");
      publish();
    });
    source.addEventListener("status", (event) => {
      const data = JSON.parse((event as MessageEvent<string>).data) as { status: RunStatus; stage: string | null };
      setState((s) => ({ ...s, status: data.status, stage: data.stage }));
    });
    source.addEventListener("done", (event) => {
      const data = JSON.parse((event as MessageEvent<string>).data) as {
        status: RunStatus; edition: EditionKind; error: string | null;
      };
      source.close();
      setState((s) => ({ ...s, status: data.status, stage: null, edition: data.edition, error: data.error, done: true }));
    });
    source.onerror = () => {
      // CONNECTING means the browser is already retrying; the replay keeps that correct.
      if (source.readyState !== EventSource.CLOSED) return;
      fetchPaper(agentId).then(
        (paper) => {
          const exists = paper.editions.some((e) => e.run_id === runId);
          setState((s) => (exists
            ? { ...s, error: s.error ?? "Lost the connection to this edition.", done: true }
            : { ...s, notFound: true, done: true }));
        },
        (error: unknown) => setState((s) => ({
          ...s, notFound: error instanceof NotFoundError, error: s.error ?? "Couldn't load this edition.", done: true,
        })),
      );
    };
    return () => source.close();
  }, [runId, agentId]);

  return state;
}
