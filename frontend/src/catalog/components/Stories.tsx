import { useId } from "react";
import type { ComponentFn } from "@json-render/react";
import type { catalog } from "../catalog";
import { ControlCircle } from "../../ui/ControlCircle";
import { Cites, UpdateTag, outletsLabel, useControlNumber, useCoverage } from "./shared";
import styles from "./catalog.module.css";

export const LeadStory: ComponentFn<typeof catalog, "LeadStory"> = ({ props }) => {
  const n = useControlNumber();
  const id = useId();
  const { outlets, update } = useCoverage(props.cites);
  return (
    <section className={styles.lead} data-kind="LeadStory" aria-labelledby={id}>
      <div className={styles.marker}><ControlCircle number={n} rings={outlets} size="lead" live /></div>
      <p className={styles.kickers}>
        <span className={styles.mainStory}>Main story</span>
        {props.kicker && <span className={styles.kicker}>{props.kicker}</span>}
        {update && <UpdateTag />}
      </p>
      <h2 id={id} className={styles.leadHeadline}>{props.headline}</h2>
      <p className={styles.dek}>{props.dek}</p>
      {props.body.map((paragraph, i) => <p key={i} className={styles.body}>{paragraph}</p>)}
      <p className={styles.coverage}>
        {outlets > 0 && <span>{outletsLabel(outlets)}</span>} <Cites cites={props.cites} />
      </p>
    </section>
  );
};

export const Story: ComponentFn<typeof catalog, "Story"> = ({ props }) => {
  const n = useControlNumber();
  const id = useId();
  const { outlets, update } = useCoverage(props.cites);
  return (
    <section className={styles.story} data-kind="Story" data-weight={props.weight} aria-labelledby={id}>
      <div className={styles.marker}><ControlCircle number={n} rings={outlets} size="story" live /></div>
      {(props.kicker || update) && (
        <p className={styles.kickers}>
          {props.kicker && <span className={styles.kicker}>{props.kicker}</span>}
          {update && <UpdateTag />}
        </p>
      )}
      <h3 id={id} className={styles.storyHeadline}>{props.headline}</h3>
      <p className={styles.dek}>{props.dek}</p>
      <p className={styles.coverage}>
        {outlets > 0 && <span>{outletsLabel(outlets)}</span>} <Cites cites={props.cites} />
      </p>
    </section>
  );
};
