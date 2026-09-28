import { createContext, useContext, type ReactNode } from "react";
import { outlet, outletsOf } from "../../lib/outlets";
import { useSources } from "../../paper/sources";
import { ControlCircle } from "../../ui/ControlCircle";
import styles from "./catalog.module.css";

/** Control number of the block being rendered (1-based reading order), set by Page. */
export const ControlNumber = createContext(0);
export const useControlNumber = () => useContext(ControlNumber);

export function useCoverage(cites: number[]): { outlets: number; update: boolean } {
  const sources = useSources();
  const cited = sources.filter((s) => cites.includes(s.n));
  return { outlets: outletsOf(cites, sources).size, update: cited.some((s) => s.seen_before) };
}

export function outletsLabel(n: number): string {
  return `Reported by ${n} ${n === 1 ? "outlet" : "outlets"}`;
}

/**
 * The control on the rail: rings counted from the block's cites, like the
 * control table, and "Update" marked on the course under it in thicket ink.
 */
export function Marker({ cites, size = "story" }: { cites: number[]; size?: "lead" | "story" }) {
  const { outlets, update } = useCoverage(cites);
  return (
    <div className={styles.marker}>
      <ControlCircle number={useControlNumber()} rings={outlets} size={size} live />
      {update && <span className={styles.update}>Update</span>}
    </div>
  );
}

/** The line under a control's text: what it is, who reported it, and its sources. */
export function Coverage({ cites, children }: { cites: number[]; children?: ReactNode }) {
  const { outlets } = useCoverage(cites);
  return (
    <p className={styles.coverage}>
      {children}
      {outlets > 0 && <span className={styles.part}>{outletsLabel(outlets)}</span>} <Cites cites={cites} />
    </p>
  );
}

/** Source numbers as links to the original articles (one click to the source). */
export function Cites({ cites }: { cites: number[] }) {
  const sources = useSources();
  return (
    <span className={styles.cites}>
      {cites.map((n) => {
        const source = sources.find((s) => s.n === n);
        return source ? (
          <a key={n} className={styles.cite} href={source.url} target="_blank" rel="noopener noreferrer"
            aria-label={`Source ${n}: ${outlet(source.url)}`} title={source.title}>{n}</a>
        ) : (
          <span key={n} className={styles.cite}>{n}</span>
        );
      })}
    </span>
  );
}
