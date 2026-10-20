# Level 2 — Container

**Question:** what are the deployable/runtime units that make up HPC Pilot, and
how do they communicate?

The system decomposes into three runtime units: the **Manager web app** (a
single Flask process), a **per-user InterLink pod** in Kubernetes, and an
**HPC edge agent** on each HPC edge-node.

```mermaid
C4Container
    title HPC Pilot — Container (Level 2)

    Person(user, "Researcher / Operator", "Web browser")

    System_Boundary(pilot, "HPC Pilot") {
        Container(manager, "Manager Web App", "Python 3 / Flask", "Single Flask process: web GUI (app), REST API (api), business logic (lib). Orchestrates jobs, InterLink pods, and HPC nodes.")
        Container(interlink_pod, "InterLink Pod", "Go containers, one per user", "wstunnel server + InterLink API server (virtual-kubelet). Forwards Kubernetes pods to HPC batch jobs.")
        Container(hpc_agent, "HPC Edge Agent", "Python, wstunnel, supervisord", "wstunnel client + supervisord + InterLink plugin (echo / docker / slurm).")
    }

    System_Ext(checkin, "EGI Check-in", "OIDC / OAuth2 identity provider")
    System_Ext(k8s, "Kubernetes Cluster", "Cloud platform hosting the manager and InterLink pods")
    System_Ext(hpc, "HPC Cluster", "Edge-nodes + batch systems")

    Rel(user, manager, "Uses web GUI", "HTTPS")
    Rel(manager, checkin, "Validates JWT, fetches JWKS / UserInfo", "HTTPS")
    Rel(manager, k8s, "Creates namespaces, deploys InterLink pods and workloads", "K8s API / Helm CLI")
    Rel(manager, hpc_agent, "Installs and manages the agent", "SSH (mccli)")
    Rel(k8s, interlink_pod, "Runs the pod (one namespace per user)", "Kubernetes")
    Rel(hpc, hpc_agent, "Runs agent + batch jobs", "local")
    Rel(interlink_pod, hpc_agent, "Job control + output (tunneled)", "WebSocket (wstunnel)")
```

## Containers

| Container | Technology | Responsibility | Deployed by |
|---|---|---|---|
| Manager Web App | Python 3 / Flask | UI, REST API, orchestration, auth | `charts/manager/` (or local dev) |
| InterLink Pod | Go (interLink + wstunnel) | virtual-kubelet that forwards pods to HPC | Manager, per user (`charts/interlink/` values) |
| HPC Edge Agent | Python + wstunnel + supervisord | wstunnel client + InterLink plugin | Manager via `mccli` (SSH) |

## Key flows

- **Job submission** — user → manager → K8s `Deployment` pinned to the
  InterLink virtual-kubelet → InterLink forwards it over wstunnel to the HPC
  plugin, which runs the batch job.
- **Tunnel setup** — the HPC edge agent's wstunnel *client* connects back to the
  InterLink pod's wstunnel *server* using path-prefix routing on the shared
  `site.hostname` (`<hostname>/<namespace>`), so no wildcard DNS/TLS is needed.
