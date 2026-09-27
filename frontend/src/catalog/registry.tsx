import { defineRegistry } from "@json-render/react";
import { catalog } from "./catalog";
import { Analysis, Briefs, Figures, Split, Timeline } from "./components/Blocks";
import { Page } from "./components/Page";
import { LeadStory, Story } from "./components/Stories";

export const { registry } = defineRegistry(catalog, {
  components: { Page, LeadStory, Story, Briefs, Split, Figures, Timeline, Analysis },
});
