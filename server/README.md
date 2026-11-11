# Pilot API — Server

The REST API service that powers HPC Pilot: it submits HPC jobs (container
workloads forwarded to HPC batch systems via
[interLink](https://interlink-project.dev)), deploys per-user InterLink pods,
manages the HPC edge-node wstunnel client, and authenticates via
[EGI Check-in](https://www.egi.eu/service/check-in/).

It can run **outside** the cluster (local dev / VM, external kubeconfig) or
**inside** the cluster as a Deployment managed by the
[pilot-deploy Helm chart](https://github.com/chbrandt/pilot-deploy/tree/main/charts/manager).

> For the full documentation see [`../docs/README.md`](../docs/README.md).

---

## Two-layer architecture

```
server/
├── lib/       # Pure Python business logic (importable from CLI)
├── api/       # JSON REST API under /api   (cURL / HTTP clients)
├── hpc/       # Runtime templates shipped to the HPC edge-node
├── k8s/       # In-cluster fixtures
├── main.py    # Flask application entry point (wires lib+api)
└── pilot_config.yaml # Unified config: site, default charts, HPC nodes
```

- `lib/` — Kubernetes SDK, `helm` CLI, `mccli`/SSH, JWT validation. No Flask.
- `api/` — thin JSON wrappers over `lib/`, protected by Bearer-token auth,
  plus public endpoints (`GET /api/site`, `POST /api/auth/*`) so the
  [Pilot App](https://github.com/chbrandt/pilot-app) GUI never validates
  JWTs locally and never sees the OIDC client secret.

See [`../docs/architecture.md`](../docs/architecture.md).

---

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure the site (single hostname — no wildcard DNS needed)
#    edit pilot_config.yaml: site.hostname, site.wstunnel.port, site.wstunnel.local_port

# 3. Set kubeconfig (optional — defaults to ~/.kube/config)
export KUBECONFIG=/path/to/your/kubeconfig

# 4. Run
python main.py
# → http://localhost:5000  (Swagger UI at /api/docs)

# Or with a custom configuration file:
python main.py --config /path/to/pilot_config.yaml

# Then run the GUI (pilot-app repository) against this API:
#   API_BASE_URL=http://localhost:5000 python main.py
```

---

## Configuration

| Source | Purpose |
|---|---|
| `pilot_config.yaml` (`site` section) | `hostname`, `wstunnel.port`, `wstunnel.local_port`, `allowed_groups` |
| `pilot_config.yaml` (`charts` section) | Default InterLink chart preset seeded per user |
| `pilot_config.yaml` (`hpc.nodes` section) | One entry per HPC node (`hostname`, `ssh_port`, `plugin`) |

| Environment variable | Default | Description |
|---|---|---|
| `KUBECONFIG` | `~/.kube/config` | Path to kubeconfig (or in-cluster ServiceAccount) |
| `FLASK_SECRET_KEY` | `dev-secret-change-in-production` | Session cookie key — **change in production** |
| `FLASK_PORT` | `5000` | TCP port |
| `FLASK_DEBUG` | `0` | `1` for debug mode |
| `PILOT_CONFIG_PATH` | `server/pilot_config.yaml` | Path to the unified config file (overridden by `--config`) |
| `PILOT_OIDC_CLIENT_SECRET` | — | Overrides `site.oidc.client_secret` for confidential OIDC clients |

See [`../docs/configuration.md`](../docs/configuration.md).

---

## Further reading

- [Deployment Guide](../docs/deployment.md)
- [REST API Reference](../docs/rest_api.md) (also at `/api/docs`)
- [Python Library](../docs/lib.md)
- [Authentication](../docs/authentication.md)
- [pilot-app](https://github.com/chbrandt/pilot-app) — the web GUI
- [pilot-deploy](https://github.com/chbrandt/pilot-deploy) — Helm charts and deployment recipes
