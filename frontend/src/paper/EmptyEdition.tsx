import styles from "./paper.module.css";

export function EmptyEdition({ answer }: { answer: string | null }) {
  return (
    <section className={styles.empty}>
      <h2>Nothing to report</h2>
      <p>{answer ?? "No news was found in this window."}</p>
    </section>
  );
}
