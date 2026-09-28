import { useId } from "react";
import type { ComponentFn } from "@json-render/react";
import type { catalog } from "../catalog";
import { Coverage, Marker } from "./shared";
import styles from "./catalog.module.css";

export const LeadStory: ComponentFn<typeof catalog, "LeadStory"> = ({ props }) => {
  const id = useId();
  return (
    <section className={styles.lead} data-kind="LeadStory" aria-labelledby={id}>
      <Marker cites={props.cites} size="lead" />
      <h2 id={id} className={styles.leadHeadline}>{props.headline}</h2>
      <p className={styles.dek}>{props.dek}</p>
      {props.body.map((paragraph, i) => <p key={i} className={styles.body}>{paragraph}</p>)}
      <Coverage cites={props.cites}>
        <span className={`${styles.part} ${styles.mainStory}`}>Main story</span>
        {props.kicker && <span className={styles.part}>{props.kicker}</span>}
      </Coverage>
    </section>
  );
};

export const Story: ComponentFn<typeof catalog, "Story"> = ({ props }) => {
  const id = useId();
  return (
    <section className={styles.story} data-kind="Story" data-weight={props.weight} aria-labelledby={id}>
      <Marker cites={props.cites} />
      <h3 id={id} className={styles.storyHeadline}>{props.headline}</h3>
      <p className={styles.dek}>{props.dek}</p>
      <Coverage cites={props.cites}>
        {props.kicker && <span className={styles.part}>{props.kicker}</span>}
      </Coverage>
    </section>
  );
};
