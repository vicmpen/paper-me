import styles from "./ui.module.css";

/** The course start: a triangle, where the bottom line sits. */
export function StartTriangle() {
  return (
    <svg className={styles.mark} viewBox="0 0 40 36" aria-hidden="true">
      <path d="M20 3 L37 33 L3 33 Z" className={styles.courseStroke} />
    </svg>
  );
}

/** The course finish: a double circle, after the last control. */
export function FinishCircle() {
  return (
    <svg className={styles.mark} viewBox="0 0 40 40" aria-hidden="true">
      <circle cx="20" cy="20" r="17" className={styles.courseStroke} />
      <circle cx="20" cy="20" r="11" className={styles.courseStroke} />
    </svg>
  );
}
