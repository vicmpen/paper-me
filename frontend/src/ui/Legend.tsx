import { LEGEND } from "./inks";
import styles from "./ui.module.css";

export function Legend() {
  return (
    <dl className={styles.legend}>
      {LEGEND.map((entry) => (
        <div key={entry.token} className={styles.legendRow}>
          <dt><span className={styles.swatch} style={{ background: `var(${entry.token})` }} aria-hidden="true" /></dt>
          <dd>{entry.label}</dd>
        </div>
      ))}
    </dl>
  );
}
