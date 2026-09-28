import { useEffect, useState } from "react";
import { createSpecStreamCompiler, type Spec } from "@json-render/core";
import { EditionView } from "../catalog/EditionView";
import { BackIssues } from "../paper/BackIssues";
import { ControlTable } from "../paper/ControlTable";
import { EmptyEdition } from "../paper/EmptyEdition";
import { Masthead } from "../paper/Masthead";
import { StaticSources } from "../paper/sources";
import { Legend } from "../ui/Legend";
import { FIXTURES, toSpec, type Fixture } from "./fixtures";
import styles from "./styleguide.module.css";

/** Replays a fixture line by line, looping, to check how blocks arrive. */
function StreamReplay({ fixture }: { fixture: Fixture }) {
  const [spec, setSpec] = useState<Spec | null>(null);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setSpec(toSpec(fixture.lines));
      return;
    }
    const compiler = createSpecStreamCompiler<Spec>();
    let i = 0;
    const timer = window.setInterval(() => {
      if (i === fixture.lines.length + 4) {
        compiler.reset();
        i = -1; // the increment below brings it to 0, so the next tick pushes the first line again
      } else if (i < fixture.lines.length) {
        compiler.push(fixture.lines[i] + "\n");
      }
      i += 1;
      const result = compiler.getResult();
      setSpec(result.root ? { ...result } : null);
    }, 700);
    return () => window.clearInterval(timer);
  }, [fixture]);
  return <StaticSources sources={fixture.sources}><EditionView spec={spec} /></StaticSources>;
}

export function Styleguide() {
  return (
    <main className={styles.guide}>
      <header className={styles.header}>
        <h1>Paper components</h1>
        <p>Every catalog component, rendered from fixture editions (synthetic content).</p>
      </header>
      <section className={styles.section} aria-labelledby="legend">
        <h2 id="legend">Legend</h2>
        <Legend />
      </section>
      <section className={styles.section} aria-labelledby="replay">
        <h2 id="replay">Going to press (replay)</h2>
        <StreamReplay fixture={FIXTURES[0]} />
      </section>
      <section className={styles.section} aria-labelledby="page-parts">
        <h2 id="page-parts">Page parts</h2>
        {/* Going to press, mid-run: the legs that a real run would otherwise have to pay for. */}
        <Masthead paper={{ agent: { id: 3, name: "Oil desk", query: "oil prices" }, current_run_id: 13, editions: [] }}
          edition={null} number={4} stage="writing" live running onPress={() => {}} pressError={null} />
        <StaticSources sources={FIXTURES[0].sources}><ControlTable spec={toSpec(FIXTURES[0].lines)} /></StaticSources>
        <BackIssues agentId={3} runId={12} editions={[
          { run_id: 12, started_at: "2026-09-27T07:00:00Z", finished_at: "2026-09-27T07:01:00Z", status: "succeeded", edition: "composed", error: null, answer: null },
          { run_id: 11, started_at: "2026-09-26T07:00:00Z", finished_at: "2026-09-26T07:00:30Z", status: "failed", edition: null, error: "search provider failed", answer: null },
          { run_id: 10, started_at: "2026-09-25T07:00:00Z", finished_at: "2026-09-25T07:01:00Z", status: "succeeded", edition: "fallback", error: null, answer: null },
        ]} />
        <EmptyEdition answer="No results found in this window." />
      </section>
      {FIXTURES.map((fixture) => (
        <section key={fixture.id} className={styles.section} aria-labelledby={`fixture-${fixture.id}`}>
          <h2 id={`fixture-${fixture.id}`}>{fixture.title}</h2>
          <p className={styles.note}>{fixture.note}</p>
          <StaticSources sources={fixture.sources}><EditionView spec={toSpec(fixture.lines)} /></StaticSources>
        </section>
      ))}
    </main>
  );
}
