import { outlet } from "../lib/outlets";
import { useSources } from "./sources";
import styles from "./paper.module.css";

export function SourcesList() {
  const sources = useSources();
  if (sources.length === 0) return null;
  return (
    <section className={styles.sources} aria-labelledby="sources-heading">
      <h2 id="sources-heading">Sources</h2>
      <ol>
        {sources.map((s) => (
          <li key={s.n} id={`source-${s.n}`} value={s.n}>
            <a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a>{" "}
            <span className={styles.railMeta}>{outlet(s.url)}{s.published && ` · ${s.published}`}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
