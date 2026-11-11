# Pilot API

The **REST API service** of HPC Pilot — the component that talks to
Kubernetes, Helm, remote HPC edge-nodes (via `mccli`/SSH) and EGI Check-in.
It is consumed by [pilot-app](https://github.com/chbrandt/pilot-app) (the web
GUI) over HTTP, and by any `curl`/HTTP client with a Bearer token.

HPC Pilot builds on top of [interLink](https://interlink-project.dev) to
manage cloud-native jobs in HPC appliances for EGI communities through
[Check-in](https://www.egi.eu/service/check-in/).

## Repository layout

```
.
├── server/            # Flask REST API (lib + api layers)
│   ├── lib/           #   business logic: k8s, helm, hpc, JWT/token auth
│   ├── api/           #   JSON endpoints under /api + Swagger UI
│   ├── hpc/  k8s/     #   runtime fixtures for HPC edge deployments
│   └── main.py        #   entry point (--config flag / PILOT_CONFIG_PATH)
├── docs/              # documentation (MkDocs site)
├── tests/             # pytest suite (api / lib)
├── Dockerfile         # image: ghcr.io/chbrandt/pilot-api
└── .github/workflows/ # CI: pr / release / test-branch
```

## Quick start

```bash
# 1. Install dependencies
pip install -r server/requirements.txt

# 2. Configure the site — edit server/pilot_config.yaml
#    (site.hostname, site.wstunnel.port, site.wstunnel.local_port)

# 3. Set kubeconfig (optional — defaults to ~/.kube/config)
export KUBECONFIG=/path/to/your/kubeconfig

# 4. Run
python server/main.py
# → http://localhost:5000  (Swagger UI at /api/docs)

# Or with a custom configuration file:
python server/main.py --config /path/to/pilot_config.yaml
```

Then start the GUI (pilot-app repository) against this API:

```bash
API_BASE_URL=http://localhost:5000 python main.py   # in pilot-app
```

## HTTP API

- Swagger UI: [`GET /api/docs`](http://localhost:5000/api/docs)
  (spec at `GET /api/openapi.yaml`)
- **Public**: `GET /health`, `GET /api/site`,
  `POST /api/auth/verify`, `POST /api/auth/oidc/exchange`
- **Protected** (Bearer token): jobs, InterLink nodes, HPC nodes,
  userspace, saved configurations — see [`docs/rest_api.md`](docs/rest_api.md).

## Related repositories

| Repository | Role |
|---|---|
| **pilot-api** (this repo) | REST API server |
| [pilot-app](https://github.com/chbrandt/pilot-app) | Web GUI — a pure HTTP client of this API |
| [pilot-deploy](https://github.com/chbrandt/pilot-deploy) | Helm charts + docker/deployment recipes |

## Continuous Integration

This repository includes GitHub Actions workflows:

- `release.yml` — publishes `ghcr.io/chbrandt/pilot-api` from version tags
  shaped like `v<MAJOR>[.<MINOR>[.<PATCH>]][-<pre-release>]` (e.g. `v2`,
  `v1.7`, `v1.2.3`, `v2-alpha`), also via manual `workflow_dispatch`.
- `test-branch.yml` — validates the `test` branch and pushes a
  `test-<sha>` image tag.
- `pr.yml` — runs unit tests and Docker build validation for pull requests,
  without publishing artifacts.

## Documentation

The full documentation lives under [`docs/`](./docs/). Start with
[`docs/README.md`](docs/README.md),
[`docs/deployment.md`](docs/deployment.md) and
[`docs/rest_api.md`](docs/rest_api.md) (also browsable at `/api/docs`).
