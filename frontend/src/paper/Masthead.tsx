import type { EditionSummary, Paper } from "../api";
import { ContourField } from "../ui/ContourField";
import { STAGES, formatDate } from "./describe";
import styles from "./paper.module.css";

export function Masthead({ paper, edition, number, stage, live, running, onPress, pressError }: {
  paper: Paper; edition: EditionSummary | null; number: number | null; stage: string | null;
  live: boolean; running: boolean; onPress: () => void; pressError: string | null;
}) {
  return (
    <header className={styles.masthead}>
      <ContourField seed={paper.agent.id} className={styles.contours} />
      <div className={styles.titleBlock}>
        <h1 className={styles.name}>{paper.agent.name}</h1>
        <p className={styles.meta}>
          {number ? `Edition ${number}` : "No editions yet"}
          {edition && ` · ${formatDate(edition.started_at)}`}
        </p>
      </div>
      {live && (
        <ol className={styles.legs} aria-label="Going to press">
          {STAGES.map((s) => (
            <li key={s.id} aria-current={s.id === stage ? "step" : undefined}
              data-state={s.id === stage ? "current" : STAGES.findIndex((x) => x.id === stage) > STAGES.findIndex((x) => x.id === s.id) ? "done" : "todo"}>
              {s.label}
            </li>
          ))}
        </ol>
      )}
      <div className={styles.press}>
        <button type="button" className={styles.pressButton} onClick={onPress} disabled={running}>
          {running ? "Going to press…" : "Go to press"}
        </button>
        {pressError && <p role="alert" className={styles.pressError}>{pressError}</p>}
      </div>
    </header>
  );
}
