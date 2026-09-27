import { Children } from "react";
import type { ComponentFn } from "@json-render/react";
import type { catalog } from "../catalog";
import { StartTriangle } from "../../ui/marks";
import { Cites, ControlNumber } from "./shared";
import styles from "./catalog.module.css";

export const Page: ComponentFn<typeof catalog, "Page"> = ({ props, children }) => (
  <article className={styles.page}>
    {props.bottomLine && (
      <p className={styles.bottomLine}>
        <StartTriangle />
        <span>
          <span className={styles.label}>Bottom line</span> {props.bottomLine.text}{" "}
          <Cites cites={props.bottomLine.cites} />
        </span>
      </p>
    )}
    <ol className={styles.course}>
      {Children.map(children, (child, i) => (
        <ControlNumber.Provider value={i + 1}>
          <li className={styles.leg}>{child}</li>
        </ControlNumber.Provider>
      ))}
    </ol>
  </article>
);
