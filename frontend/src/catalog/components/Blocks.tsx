import { useId } from "react";
import type { ComponentFn } from "@json-render/react";
import type { catalog } from "../catalog";
import { ControlCircle } from "../../ui/ControlCircle";
import { FinishCircle } from "../../ui/marks";
import { Cites, useControlNumber } from "./shared";
import styles from "./catalog.module.css";

// Drawn arrows, not ▲/▼ glyphs: a triangle is the course start mark.
const ARROW = { up: "M8 14V2M3 7l5-5 5 5", down: "M8 2v12M3 9l5 5 5-5", neutral: "M2 8h12" } as const;

function Direction({ direction }: { direction: keyof typeof ARROW }) {
  return <svg className={styles.direction} viewBox="0 0 16 16" aria-hidden="true"><path d={ARROW[direction]} /></svg>;
}

function Marker() {
  return <div className={styles.marker}><ControlCircle number={useControlNumber()} rings={0} size="small" live /></div>;
}

export const Briefs: ComponentFn<typeof catalog, "Briefs"> = ({ props }) => {
  const id = useId();
  return (
    <section className={styles.block} data-kind="Briefs" aria-labelledby={id}>
      <Marker />
      <h3 id={id} className={styles.blockTitle}>{props.title}</h3>
      <ul className={styles.list}>
        {props.items.map((item, i) => <li key={i}>{item.text} <Cites cites={item.cites} /></li>)}
      </ul>
    </section>
  );
};

export const Split: ComponentFn<typeof catalog, "Split"> = ({ props }) => {
  const id = useId();
  return (
    <section className={styles.block} data-kind="Split" aria-labelledby={id}>
      <Marker />
      <h3 id={id} className={styles.blockTitle}>{props.title}</h3>
      <div className={styles.ridge}>
        {props.sides.map((side, i) => (
          <div key={i} className={styles.side} data-direction={side.direction}>
            <h4 className={styles.sideLabel}><Direction direction={side.direction} /> {side.label}</h4>
            <ul className={styles.list}>
              {side.points.map((point, j) => <li key={j}>{point.text} <Cites cites={point.cites} /></li>)}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
};

export const Figures: ComponentFn<typeof catalog, "Figures"> = ({ props }) => (
  <section className={styles.block} data-kind="Figures" aria-label="Key figures">
    <Marker />
    <dl className={styles.figures}>
      {props.items.map((item, i) => (
        <div key={i} className={styles.figure}>
          <dt className={styles.figureLabel}>{item.label}</dt>
          <dd className={styles.figureValue}>{item.value} <Cites cites={item.cites} /></dd>
        </div>
      ))}
    </dl>
  </section>
);

export const Timeline: ComponentFn<typeof catalog, "Timeline"> = ({ props }) => {
  const id = useId();
  return (
    <section className={styles.block} data-kind="Timeline" aria-labelledby={id}>
      <Marker />
      <h3 id={id} className={styles.blockTitle}>{props.title}</h3>
      <ol className={styles.timeline}>
        {props.events.map((event, i) => (
          <li key={i}><span className={styles.date}>{event.date}</span> {event.text} <Cites cites={event.cites} /></li>
        ))}
      </ol>
    </section>
  );
};

export const Analysis: ComponentFn<typeof catalog, "Analysis"> = ({ props }) => {
  const id = useId();
  return (
    <section className={styles.analysis} data-kind="Analysis" aria-labelledby={id}>
      <div className={styles.marker}><FinishCircle /></div>
      <h3 id={id} className={styles.blockTitle}>{props.heading}</h3>
      {props.paragraphs.map((paragraph, i) => <p key={i} className={styles.body}>{paragraph}</p>)}
      <p className={styles.coverage}><Cites cites={props.cites} /></p>
    </section>
  );
};
