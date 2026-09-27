import { useEffect, useState } from "react";
import { createSpecStreamCompiler, type Spec } from "@json-render/core";
import { EditionView } from "../catalog/EditionView";
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
        i = 0;
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
