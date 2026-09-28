import type { Spec } from "@json-render/core";
import { useSources } from "./sources";
import { KIND_LABEL, controlRows, formatRead, type Freshness } from "./describe";
import styles from "./paper.module.css";

const FRESHNESS: Record<Exclude<Freshness, null>, string> = { new: "New", update: "Update", continuing: "Continuing" };

export function ControlTable({ spec }: { spec: Spec | null }) {
  const rows = controlRows(spec, useSources());
  if (rows.length === 0) return null;
  return (
    <table className={styles.controls}>
      <caption>Control descriptions</caption>
      <thead>
        <tr><th scope="col">No.</th><th scope="col">Control</th><th scope="col">Outlets</th><th scope="col">Read</th><th scope="col">Status</th></tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td className={styles.number}>{row.number}</td>
            <th scope="row">
              <span className={styles.kind}>{KIND_LABEL[row.kind] ?? row.kind}</span>
              {row.label !== KIND_LABEL[row.kind] && <> {row.label}</>}
            </th>
            <td>{row.outlets || "—"}</td>
            <td className={styles.nowrap}>{formatRead(row.readSeconds)}</td>
            {/* The ink is a swatch beside the word, never the only cue: open and thicket are too light for text. */}
            <td className={styles.nowrap} data-freshness={row.freshness ?? undefined}>
              {row.freshness ? <><span className={styles.freshMark} aria-hidden="true" />{FRESHNESS[row.freshness]}</> : "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
