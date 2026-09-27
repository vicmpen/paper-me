import { z } from "zod";
import { defineCatalog } from "@json-render/core";
import { schema } from "@json-render/react/schema";

// The single definition of the paper's components. Python reads the exported
// copies in webapp/catalog/ (npm run export-catalog); never edit those by hand.

/** Source numbers (1-based positions in the run's sources). The backend checks each is within 1..k for the run. */
export const cites = z.array(z.number().int().min(1).max(40)).min(1).max(10);

const cited = (max: number) => z.object({ text: z.string().max(max), cites });

const side = z.object({
  label: z.string().max(40),
  direction: z.enum(["up", "down", "neutral"]),
  points: z.array(cited(500)).min(1).max(6),
});

export const catalog = defineCatalog(schema, {
  components: {
    Page: {
      props: z.object({ bottomLine: cited(280).optional() }),
      slots: ["default"],
      description:
        "The root of the edition. Its children are the edition's blocks in reading order. " +
        "bottomLine is optional: one sentence stating the one thing to know from this edition.",
    },
    LeadStory: {
      props: z.object({
        kicker: z.string().max(40).optional(),
        headline: z.string().max(160),
        dek: z.string().max(400),
        body: z.array(z.string().max(1200)).min(1).max(3),
        cites,
      }),
      slots: [],
      description:
        "The main story: the event reported by the most independent outlets. At most one, and only when " +
        "one story clearly leads. When present it is the first child of Page. cites lists every source " +
        "that reports this event.",
    },
    Story: {
      props: z.object({
        kicker: z.string().max(40).optional(),
        headline: z.string().max(160),
        dek: z.string().max(400),
        cites,
        weight: z.enum(["major", "minor"]),
      }),
      slots: [],
      description: "A story. weight: major for a significant development, minor for a smaller one.",
    },
    Briefs: {
      props: z.object({ title: z.string().max(40), items: z.array(cited(500)).min(1).max(8) }),
      slots: [],
      description: "Short one-line items, each with its own cites.",
    },
    Split: {
      props: z.object({ title: z.string().max(80), sides: z.array(side).length(2) }),
      slots: [],
      description:
        "Two opposing sides, e.g. what pushes a price up versus down, or arguments for and against. " +
        "Use only when the sources describe forces in opposite directions.",
    },
    Figures: {
      props: z.object({
        items: z
          .array(z.object({ value: z.string().max(24), label: z.string().max(80), cites }))
          .min(1)
          .max(4),
      }),
      slots: [],
      description: "Key numbers, written exactly as the sources state them.",
    },
    Timeline: {
      props: z.object({
        title: z.string().max(80),
        events: z
          .array(z.object({ date: z.string().max(24), text: z.string().max(500), cites }))
          .min(2)
          .max(10),
      }),
      slots: [],
      description: "A dated sequence of events, oldest first.",
    },
    Analysis: {
      props: z.object({
        heading: z.string().max(60),
        paragraphs: z.array(z.string().max(1200)).min(1).max(3),
        cites,
      }),
      slots: [],
      description: "What the news means, drawn only from the cited sources. Clearly labelled synthesis.",
    },
  },
  // The paper is read-only: no actions.
  actions: {},
});
