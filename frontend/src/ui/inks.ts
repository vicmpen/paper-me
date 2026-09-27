/** Each map ink means exactly one thing on the paper. */
export const LEGEND = [
  { token: "--course", label: "Course and controls: the reading order, what is live, links" },
  { token: "--contour", label: "Contour rings: one per independent outlet" },
  { token: "--open", label: "New since the last edition" },
  { token: "--thicket", label: "Continuing story, updated" },
  { token: "--water", label: "What it means" },
] as const;
