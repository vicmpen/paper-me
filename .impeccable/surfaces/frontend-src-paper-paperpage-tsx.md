---
version: 1
slug: "frontend-src-paper-paperpage-tsx"
primary_target: "frontend/src/paper/PaperPage.tsx"
related_targets: ["frontend/src/styleguide/Styleguide.tsx"]
---

# Surface brief: the paper (/paper/:agentId)

Scope: one agent's paper. The latest edition, streaming live while it is
composed, plus back issues and the component styleguide. Visitor mode: Read.

Audience and job: domain trackers first, everyday readers second, on phone and
desktop equally, at any time of day, often arriving from a "new edition"
notification. The job is fast orientation (what happened, what matters most),
what changed since the last edition, and trust (every claim is one tap from
its source).

Constraints: content is text only and comes from the json-render catalog
(LeadStory, Story, Briefs, Split, Figures, Timeline, Analysis); there is no
imagery. The main story is optional and earned by the number of independent
outlets. Light and dark are both first-class. Anti-goals: a generic SaaS
dashboard, retro costume, too dense for everyday readers, too airy for
trackers.

## Direction contract

THESIS: Each paper is a course set over the terrain of its beat. Stories are
numbered controls on a purple course, and coverage is contour: one ring per
independent outlet, so the main story stands as the summit. It refuses the
broadsheet front page and the card feed.

OWN-WORLD: ISOM inks on runnable-forest white, never cream. Course purple owns
the course line, the controls and the live leg. Contour brown, open-land
yellow, thicket green and marsh blue form a fixed legend, and each ink means
one thing. Display text and numerals are set in condensed bold caps; reading
text is in a plain humanist sans. The only marks are control circles, a start
triangle and a finish double circle, and nothing is boxed. Dark mode is a
night map: the same inks on a deep ground.
Raises: a fixed contour interval (one ring per outlet, counted rather than
read), no cards or panels, up and down forces placed across one ridge line,
and changes marked on the course itself.

STORY: The reader reads the bottom line at the start triangle, sees which
control is the summit and why, follows the course, and punches any control
through to its sources.

FIRST VIEWPORT: A header strip holds the paper name in condensed caps, the
edition and the live leg, with Go to press on the right. The left eight
columns carry the start triangle and the bottom line, then control 1 at
display scale with its rings and "Reported by N sources", with the course
descending to controls 2 and 3. The right four columns carry the
control-description table: code, type, outlets, read time, new or continuing.
On mobile these become one vertical course.
SIGNATURE: When the edition goes to press, the course draws itself leg by
leg. Each arriving control punches in at full purple while placed controls
settle. The stages are named legs with patterns, never colour alone.
Reduced-motion users get the finished course.

FORM: An orienteering map and legend, the first-dealt challenger that led the
bolder-register hand. Seed key e14a4721.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- Real typefaces: the condensed display face and the reading sans. The
  reference's faces are fictional, so pick obtainable ones at build time.
- The deep ground colour for the night map, and how the contour texture is
  generated (SVG, kept away from body text).
- How the map grammar carries Figures, Timeline and Analysis.
