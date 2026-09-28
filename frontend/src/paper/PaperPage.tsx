import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { fetchPaper, goToPress, NotFoundError, type Paper } from "../api";
import { EditionView } from "../catalog/EditionView";
import { Legend } from "../ui/Legend";
import { BackIssues } from "./BackIssues";
import { ControlTable } from "./ControlTable";
import { editionNumber, hasNoLead } from "./describe";
import { EmptyEdition } from "./EmptyEdition";
import { Masthead } from "./Masthead";
import { SourcesProvider } from "./sources";
import { SourcesList } from "./SourcesList";
import { useEditionStream } from "./useEditionStream";
import styles from "./paper.module.css";

function NotFound() {
  return (
    <main className={styles.notFound}>
      <h1>This paper doesn't exist</h1>
      <p><a href="/">Back to your agents</a></p>
    </main>
  );
}

export function PaperPage() {
  const params = useParams();
  const agentId = Number(params.agentId);
  const navigate = useNavigate();
  const [paper, setPaper] = useState<Paper | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pressing, setPressing] = useState(false);
  const [pressError, setPressError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let live = true;
    fetchPaper(agentId).then(
      (loaded) => {
        if (!live) return;
        setPaper(loaded);
        setPressing(false); // the reloaded paper lists the new run as running
      },
      (error: unknown) => {
        if (!live) return;
        setPressing(false);
        if (error instanceof NotFoundError) setNotFound(true);
        else setLoadError("Couldn't load this paper. Reload to try again.");
      },
    );
    return () => {
      live = false;
    };
  }, [agentId, refresh]);

  const runId = params.runId ? Number(params.runId) : paper?.current_run_id ?? null;
  const stream = useEditionStream(runId, agentId);

  useEffect(() => {
    if (stream.done) setRefresh((r) => r + 1); // a finished run changes the back-issues rail
  }, [stream.done]);

  if (notFound || stream.notFound) return <NotFound />;
  if (!paper) return <p className={styles.loading} role={loadError ? "alert" : undefined}>{loadError ?? "Loading the paper…"}</p>;

  const latest = paper.editions[0];
  const edition = paper.editions.find((e) => e.run_id === runId) ?? null;
  const running = paper.editions.some((e) => e.status === "running");
  const empty = stream.edition === "empty" || edition?.edition === "empty";

  const onPress = async () => {
    setPressError(null);
    setPressing(true); // no second run from a double click before the paper reloads
    try {
      await goToPress(agentId);
      navigate(`/${agentId}`);
      setRefresh((r) => r + 1);
    } catch {
      setPressError("Couldn't start a run. Try again.");
      setPressing(false);
    }
  };

  return (
    <SourcesProvider runId={runId} refreshKey={`${stream.stage}-${stream.done}`}>
      <div className={styles.paper}>
        <Masthead paper={paper} edition={edition} number={editionNumber(paper.editions, runId)}
          stage={stream.stage} live={stream.status === "running"} running={running || pressing}
          onPress={onPress} pressError={pressError} />
        {!params.runId && latest?.status === "failed" && (
          <p role="status" className={styles.banner}>Latest run didn't go to press: {latest.error ?? "unknown error"}</p>
        )}
        <div className={styles.layout}>
          <main className={styles.edition}>
            {runId == null ? (
              <section className={styles.empty}>
                <h2>No edition yet</h2>
                <p>Go to press to lay out this paper's first edition.</p>
              </section>
            ) : edition?.status === "failed" ? (
              <section className={styles.empty}>
                <h2>Didn't go to press</h2>
                <p>{edition.error ?? "unknown error"}</p>
              </section>
            ) : empty ? (
              <EmptyEdition answer={edition?.answer ?? null} />
            ) : (
              <>
                {hasNoLead(stream.spec) && <p className={styles.noLead}>No single story dominates this edition.</p>}
                <EditionView spec={stream.spec} />
              </>
            )}
          </main>
          <aside className={styles.aside}>
            <ControlTable spec={stream.spec} />
            <BackIssues agentId={agentId} editions={paper.editions} runId={runId} />
          </aside>
        </div>
        <SourcesList />
        <footer className={styles.footer}><Legend /></footer>
      </div>
    </SourcesProvider>
  );
}
