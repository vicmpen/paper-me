import { z } from "zod";
import { catalog } from "./catalog";

type ComponentDef = { props: z.ZodType; description: string; slots: string[] };

function defs(): [string, ComponentDef][] {
  return Object.entries(catalog.data.components as unknown as Record<string, ComponentDef>);
}

/** Props JSON Schema per component, as written to webapp/catalog/catalog.schema.json. */
export function componentSchemas(): Record<string, object> {
  return Object.fromEntries(defs().map(([name, def]) => [name, z.toJSONSchema(def.props)]));
}

// Hand-written instead of catalog.prompt(): json-render's generated prompt
// teaches state, dynamic props, actions and invented sample data, all of
// which this paper forbids.
const FORMAT = `You lay out one edition of a personal newspaper as a stream of JSON Patch (RFC 6902) operations, one JSON object per line. Output only these lines: no prose, no Markdown, no code fences.

## Format

1. The first line sets the root:
{"op":"add","path":"/root","value":"page"}
2. The second line adds the Page element and lists every child id in reading order:
{"op":"add","path":"/elements/page","value":{"type":"Page","props":{},"children":["lead","s1","briefs"]}}
3. Then add each child, in the same order, one line each:
{"op":"add","path":"/elements/s1","value":{"type":"Story","props":{"headline":"...","dek":"...","cites":[2],"weight":"minor"},"children":[]}}

## Rules

- Every element is exactly {"type": ..., "props": ..., "children": [...]} with no other keys.
- Only Page has children. Every other element has "children": [].
- Element ids are short lowercase words: letters, digits and hyphens.
- Use only "add" operations, only on /root and /elements/<id>.
- At most 12 elements, including Page.
- Props must match the component's schema exactly. Values are plain strings, numbers and arrays; never expressions or keys starting with "$".
- cites are source numbers from the numbered sources you are given.`;

/** The catalog part of compose's system prompt, as written to webapp/catalog/catalog.prompt.txt. */
export function buildPrompt(): string {
  const components = defs().map(([name, def]) => {
    const { $schema: _unused, ...props } = z.toJSONSchema(def.props) as Record<string, unknown>;
    const children =
      def.slots.length > 0 ? "Its children are other elements, listed by id." : 'A leaf: "children" is always [].';
    return `### ${name}\n${def.description}\n${children}\nprops: ${JSON.stringify(props)}`;
  });
  return `${FORMAT}\n\n## Components\n\n${components.join("\n\n")}\n`;
}
