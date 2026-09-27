import { mkdirSync, writeFileSync } from "node:fs";
import { buildPrompt, componentSchemas } from "../src/catalog/prompt";

// Writes the catalog copies Python reads. Run after any catalog change.
const out = new URL("../../webapp/catalog/", import.meta.url);
mkdirSync(out, { recursive: true });
writeFileSync(new URL("catalog.prompt.txt", out), buildPrompt());
writeFileSync(new URL("catalog.schema.json", out), JSON.stringify(componentSchemas(), null, 2) + "\n");
console.log("wrote webapp/catalog/catalog.prompt.txt and catalog.schema.json");
