# C4 Architecture Model

This folder contains a [C4 model](https://c4model.com) of the **HPC Pilot**
codebase. The C4 model describes software architecture at increasing levels of
detail, from a high-level system context down to individual components.

## The four levels

| Level | Name | Question it answers | File |
|---|---|---|---|
| 1 | **System Context** | What does HPC Pilot do, and who/what does it talk to? | [`level1-context.md`](level1-context.md) |
| 2 | **Container** | What are the deployable/runtime units (apps, pods, agents)? | [`level2-container.md`](level2-container.md) |
| 3 | **Component** | What are the modules inside the Manager web app? | [`level3-component.md`](level3-component.md) |
| 4 | **Code** | Class/function level | _Out of scope — see below_ |

> **Level 4 (code)** is intentionally omitted: it would be a UML class diagram,
> and the dynamic behaviour is already covered by the request-lifecycle
> sequence diagrams in [`../architecture.md`](../architecture.md).

## How to view the diagrams

The diagrams are written in **Mermaid** (`C4Context` / `C4Container` /
`C4Component`), embedded as fenced code blocks (`mermaid` language tag) inside
each Markdown file. They render automatically in:

- **GitHub / GitLab** — just open the `.md` file.
- **MkDocs** — this folder is under `docs_dir: documentation`, so it becomes
  part of the published site. Mermaid rendering is enabled in `mkdocs.yml`
  (via `pymdownx.superfences`); install `requirements-docs.txt` and run
  `mkdocs build` / `mkdocs serve`.
- **VS Code** — install the *Markdown Preview Mermaid Support* extension.
- **mermaid.live** — paste a diagram block to render/export it as PNG/SVG.

## How to update the model

Edit the Mermaid block in the relevant level file. Each diagram is plain text;
the only rules are the [Mermaid C4 syntax](https://mermaid.js.org/syntax/c4.html):

- `Person` / `System` / `Container` / `Component` declare an element
  (`id`, `"name"`, `"description"`).
- `_Ext` suffix marks an element as *external* to the system (grey).
- `Rel(A, B, "label", "technology")` draws a relationship arrow.
- `System_Boundary` / `Container_Boundary` group elements.

## Legend

Mermaid C4 diagrams include a built-in legend:

- **Person** — a human user
- **System** — the system under design
- **External System** — a system outside the design (grey)
- **Container** — a deployable/runtime unit
- **Component** — a module inside a container
- Solid arrow = relationship; dashed arrow = *returns*/back relationship

## Mapping to the codebase

| C4 element | Where it lives |
|---|---|
| Manager Web App (container) | `manager/main.py` + `manager/app/` + `manager/api/` + `manager/lib/` |
| InterLink Pod (container) | Deployed from `charts/interlink/` (per-user, via `lib/helm_client.py`) |
| HPC Edge Agent (container) | Installed on HPC edge-nodes by `lib/hpc_client.py` (wstunnel + supervisord + plugin) |
| Manager Helm chart | `charts/manager/` (in-cluster deployment, ServiceAccount, Ingress) |
| Configuration | `manager/pilot_config.yaml` (`site`, `charts`, `hpc.nodes`) |

## Relation to the existing docs

The ASCII diagrams in [`../architecture.md`](../architecture.md) describe the
same system informally. These C4 diagrams are the formal, standardised view;
the two are complementary, not a replacement:

- `architecture.md` — module responsibilities + request lifecycles (dynamic view).
- `c4/` — structural decomposition (static view) at three zoom levels.
