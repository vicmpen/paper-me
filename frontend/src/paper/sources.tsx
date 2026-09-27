import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { fetchSources, type Source } from "../api";

const SourcesContext = createContext<Source[]>([]);

/**
 * Loads a run's numbered sources. refreshKey re-fetches them: sources are
 * saved before compose starts, so the page refreshes when the stage changes.
 */
export function SourcesProvider({ runId, refreshKey, children }: {
  runId: number | null; refreshKey?: unknown; children: ReactNode;
}) {
  const [sources, setSources] = useState<Source[]>([]);
  useEffect(() => {
    let live = true;
    if (runId == null) {
      setSources([]);
      return;
    }
    fetchSources(runId).then(
      (loaded) => live && setSources(loaded),
      () => live && setSources([]),
    );
    return () => {
      live = false;
    };
  }, [runId, refreshKey]);
  return <SourcesContext.Provider value={sources}>{children}</SourcesContext.Provider>;
}

/** Fixed sources, for the styleguide and tests. */
export function StaticSources({ sources, children }: { sources: Source[]; children: ReactNode }) {
  return <SourcesContext.Provider value={sources}>{children}</SourcesContext.Provider>;
}

export function useSources(): Source[] {
  return useContext(SourcesContext);
}
