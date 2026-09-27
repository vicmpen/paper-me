import { JSONUIProvider, Renderer } from "@json-render/react";
import type { Spec } from "@json-render/core";
import { registry } from "./registry";

/** Renders a (possibly partial, still streaming) edition spec. */
export function EditionView({ spec }: { spec: Spec | null }) {
  // The stream's first line sets only the root; Renderer needs elements.
  if (!spec?.root || !spec.elements) return null;
  return (
    <JSONUIProvider registry={registry}>
      <Renderer spec={spec} registry={registry} />
    </JSONUIProvider>
  );
}
