# HPC Pilot — Pilot API

HPC Pilot deploys **HPC jobs** (container workloads forwarded to HPC batch
systems via [interLink](https://interlink-project.dev)) and per-user
InterLink pods in a Kubernetes cluster, authenticating users via
[EGI Check-in](https://www.egi.eu/service/check-in/). Since the `pilot-*`
split it is composed of three repositories:

| Repository | Role |
|---|---|
| **pilot-api** (this repo) | REST API server — all Kubernetes / Helm / HPC / Check-in logic |
| [pilot-app](https://github.com/chbrandt/pilot-app) | Web GUI — a pure HTTP client of this API |
| [pilot-deploy](https://github.com/chbrandt/pilot-deploy) | Helm charts and docker/deployment recipes |

Every authenticated user gets their own isolated Kubernetes namespace.
Tokens are validated on the API side — the GUI never handles JWTs or
secrets.

## Features (API side)

| Feature | Description |
| --- | --- |
| **Job submission** | `POST /api/jobs/preset`, `POST /api/jobs/spec` — container jobs pinned to InterLink virtual-kubelet nodes |
| **InterLink deployment** | `POST/GET/DELETE /api/interlink` — one release per (user, HPC node) pair |
| **HPC node management** | `/api/hpc/*` — install/start/stop/status/uninstall the wstunnel client + supervisord + InterLink plugin on a remote HPC edge-node via `mccli` |
| **Userspace lifecycle** | `POST/DELETE /api/userspace/`, `POST /api/userspace/prune` |
| **Saved configs** | Per-user store of reusable job / chart templates, seeded on first login (`/api/saved`, `/api/saved/seed`) |
| **Public site metadata** | `GET /api/site` — display-safe site configuration for remote clients |
| **Login endpoints** | `POST /api/auth/verify`, `POST /api/auth/oidc/exchange` — let the GUI log in without any local JWT/secret handling |
| **Auth** | EGI Check-in Bearer tokens; user namespace derived deterministically from the `sub` claim |

---

## Architecture

```
server/
├── lib/       # Pure Python business logic (importable from CLI)
├── api/       # JSON REST API under /api   (cURL / HTTP clients)
├── hpc/       # Runtime templates shipped to the HPC edge-node
├── k8s/       # In-cluster fixtures
├── main.py    # Flask application entry point (wires lib+api)
└── pilot_config.yaml # Unified config: site, default charts, HPC nodes
```

See [Architecture](architecture.md) for the component diagram and request
lifecycle, and the [pilot-app repository](https://github.com/chbrandt/pilot-app)
for the GUI side.

---

## Prerequisites

| Requirement | Notes |
| --- | --- |
| Python ≥ 3.9 | Tested with 3.11 / 3.12 |
| `helm` CLI (v3) | Must be on `$PATH`; used for chart operations |
| `kubectl` access | Via `KUBECONFIG` or `~/.kube/config` (or in-cluster ServiceAccount) |
| EGI Check-in access token | For token-paste login (see the `lib/token_checkin.py` helper); alternatively configure `site.oidc` and let the GUI use the browser button |
| `pilot_config.yaml` | Operator-level settings (`site`), default charts (`charts`), HPC nodes (`hpc.nodes`) |
| `mccli` + `flaat-userinfo` | **Only for HPC operations** — install with `pip install mccli` (bundled in the Docker image) |

---

## Quick start

```bash
cd server/
pip install -r requirements.txt

# Configure the site: edit the `site` section of pilot_config.yaml
# (hostname, wstunnel.port, wstunnel.local_port)

export KUBECONFIG=/path/to/your/kubeconfig   # optional
python main.py            # → http://localhost:5000 (Swagger UI at /api/docs)
```

Then run the GUI against it (from a pilot-app checkout):

```bash
API_BASE_URL=http://localhost:5000 python main.py
```

---

## Further reading

- [**Deployment Guide**](deployment.md) — build both images, install the Helm chart (pilot-deploy), connect InterLink and the HPC edge-node end-to-end
- [Architecture](architecture.md) — component diagram and request lifecycle
- [Authentication](authentication.md) — EGI Check-in token-paste and OAuth browser login flows
- [REST API Reference](rest_api.md) — REST API endpoints (also at `/api/docs`)
- [Python Library](lib.md) — the pure-Python `lib` package
- [Kubernetes Integration](kubernetes.md) — resources created, RBAC
- [Helm Integration](helm.md) — the InterLink chart and `helm_client`
- [Configuration](configuration.md) — all environment variables, kubeconfig, RBAC, production setup
