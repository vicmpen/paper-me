import { Link } from "react-router";
import type { EditionSummary } from "../api";
import { formatDate } from "./describe";
import styles from "./paper.module.css";

export function BackIssues({ agentId, editions, runId }: { agentId: number; editions: EditionSummary[]; runId: number | null }) {
  if (editions.length === 0) return null;
  return (
    <nav className={styles.rail} aria-label="Back issues">
      <h2 className={styles.railTitle}>Back issues</h2>
      <ol>
        {editions.map((e, i) => (
          <li key={e.run_id} data-status={e.status}>
            <Link to={`/${agentId}/${e.run_id}`} aria-current={e.run_id === runId ? "page" : undefined}>
              Edition {editions.length - i}
            </Link>{" "}
            <span className={styles.railMeta}>
              {e.status === "failed" ? "Didn't go to press" : e.status === "running" ? "Going to press…" : formatDate(e.started_at)}
            </span>
          </li>
        ))}
      </ol>
    </nav>
  );
}
