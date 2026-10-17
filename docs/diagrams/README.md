# Diagrams and wireframes

Every picture here is drawn from a text source in [`src/`](src/), so it can be reviewed in a pull
request and drawn again when the product changes. Nothing is a screenshot of a drawing tool.
[SUBMISSION_ANSWERS.md](../../SUBMISSION_ANSWERS.md) explains each one in context.

| Picture | What it shows | Source |
|---|---|---|
| [01-use-cases.png](01-use-cases.png) | Use cases: what the person leaving, the person staying and a visitor do, and where Gemini helps | Mermaid |
| [02-process-flow.png](02-process-flow.png) | The whole process, from what a family says to a plan they can practise, with the review gate and the model router | Mermaid |
| [03-timeline.png](03-timeline.png) | A family's two weeks with the app, from the first voice note to the day of leaving | Mermaid |
| [04-sequence-voice-note.png](04-sequence-voice-note.png) | Sequence: a voice note from the microphone to facts waiting for review | Mermaid |
| [05-sequence-live-practice.png](05-sequence-live-practice.png) | Sequence: spoken practice with Gemini Live through a single-use token, then grading | Mermaid |
| [06-states.png](06-states.png) | The states of a fact and of a responsibility, and what moves them | Mermaid |
| [07-screen-map.png](07-screen-map.png) | The 16 screens and how people move between them | HTML |
| [08-architecture-poster.png](08-architecture-poster.png) | The architecture: browser, Cloud Run service, AI layer, engine, Google models, data, build | HTML |
| [08-architecture.png](08-architecture.png) | The same architecture as an editable Mermaid diagram | Mermaid |
| [09-deployment.png](09-deployment.png) | Deployment on Google Cloud: Cloud Build, Artifact Registry, Cloud Run, Firestore, Storage, Secret Manager | Mermaid |
| [10-engine.png](10-engine.png) | The deterministic engine: compile, evaluate, discover, the knockout test, repair and the plan search | Mermaid |
| [11-workflows.png](11-workflows.png) | The three Agent Development Kit workflows (ingest, analysis, grade) node by node | Mermaid |
| [12-router.png](12-router.png) | How the free-tier router picks a model for each request | Mermaid |
| [13-data-model.png](13-data-model.png) | The data model: a household record and everything in it | Mermaid |
| [14-security.png](14-security.png) | Security and privacy, layer by layer | HTML |
| [15-wireframe-overview.png](15-wireframe-overview.png) | Wireframe 1: the dashboard and the findings page | HTML |
| [16-wireframe-flow.png](16-wireframe-flow.png) | Wireframe 2: capture, review, plan and practise | HTML |
| [17-wireframe-phone.png](17-wireframe-phone.png) | Wireframe 3: on a phone, the handover page, spoken practice and the printed card | HTML |

Mermaid diagrams also have an `.svg` next to the `.png`.

## Drawing them again

```bash
cd apps/web
npm run diagrams              # all of them, into docs/diagrams/
npm run diagrams -- 07        # only the ones whose name contains "07"
```

or `make diagrams` from the repository root. The script opens each source in the bundled
Chromium, with the app's own fonts (Figtree and Bricolage Grotesque) embedded:

- `*.mmd` files are drawn with Mermaid 11.17.2 (from jsDelivr; set `MERMAID_JS` to a local
  `mermaid.min.js` to work offline) and saved as SVG and PNG.
- `*.html` files (the screen map, the architecture poster, the security layers and the three
  wireframe sheets) are photographed at twice their size. Their arrows are drawn by
  [`src/wires.js`](src/wires.js) from the boxes' real positions, so a box can move without
  anyone redrawing an arrow. Shared styles are in [`src/poster.css`](src/poster.css) and
  [`src/wireframe.css`](src/wireframe.css).

The colours are the app's: teal for the product, the five readiness colours where they carry
meaning, indigo for Google models, amber for data, red for guards and green for deterministic code.
