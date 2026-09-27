import { createContext, useContext } from "react";
import { outlet, outletsOf } from "../../lib/outlets";
import { useSources } from "../../paper/sources";
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

export function UpdateTag() {
  return <span className={styles.update}>Update</span>;
}
