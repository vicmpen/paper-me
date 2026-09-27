import styles from "./ControlCircle.module.css";

export const MAX_RINGS = 8;

/**
 * An orienteering control: the numbered circle, ringed by one contour per
 * independent outlet, so coverage reads by counting. Decorative; the
 * surrounding text states the number and the outlet count.
 */
export function ControlCircle({ number, rings, size = "story", live = false }: {
  number: number; rings: number; size?: "lead" | "story" | "small"; live?: boolean;
}) {
  const shown = Math.max(0, Math.min(rings, MAX_RINGS));
  return (
    <svg className={`${styles.control} ${styles[size]}`} viewBox="-60 -60 120 120"
      aria-hidden="true" data-live={live || undefined}>
      {Array.from({ length: shown }, (_, i) => (
        <circle key={i} data-ring className={styles.ring} r={24 + (i + 1) * 4.2} />
      ))}
      <circle className={styles.face} r={20} />
      <text className={styles.number} textAnchor="middle" dominantBaseline="central">{number}</text>
    </svg>
  );
}
