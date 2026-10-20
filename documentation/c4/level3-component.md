# Level 3 — Component

**Question:** what modules make up the Manager web app, and how do they fit
together?

The Manager is a single Flask process organised in three layers
(`app/` → `api/` → `lib/`), wired together by `main.py` and configured from
`pilot_config.yaml`.

## Manager Web App — top-level components

```mermaid
C4Component
    title HPC Pilot — Manager Web App Components (Level 3)

    Container_Boundary(manager, "Manager Web App") {
        Component(main, "main.py", "Flask app factory", "Registers blueprints, /health, /api/docs, injects current_user")
        Component(gui, "app/ — Web GUI", "Flask blueprints + Jinja2", "HTML routes; calls the REST API over HTTP via api_client (loopback by default)")
        Component(api, "api/ — REST API", "Flask blueprints, JSON", "/api endpoints; Bearer-token auth via require_token")
        Component(lib, "lib/ — Business Logic", "Pure Python", "K8s SDK, Helm CLI, mccli/SSH, JWT validation, config, saved deployments")
        Component(config, "pilot_config.yaml", "YAML", "site, charts, hpc.nodes configuration")
    }

    Rel(main, gui, "registers blueprints")
    Rel(main, api, "registers blueprints")
    Rel(gui, api, "HTTP calls", "API_BASE_URL (loopback)")
    Rel(api, lib, "calls business logic")
    Rel(api, config, "loads config")
    Rel(lib, config, "loads config")
```

### Blueprints (routes) per layer

| Layer | Blueprints | Endpoints |
|---|---|---|
| `app/` (GUI) | `auth_bp`, `k8s_bp`, `helm_bp`, `hpc_bp`, `saved_bp` | `/login`, `/submit`, `/nodes`, `/deployments`, `/output`, … |
| `api/` (REST) | `k8s_bp`, `helm_bp`, `hpc_bp`, `saved_bp`, `docs_bp` | `/api/jobs`, `/api/interlink`, `/api/hpc/*`, `/api/docs` |
| `main.py` | — | `/health` (public liveness probe), Swagger UI |

## `lib/` — business-logic components

```mermaid
C4Component
    title HPC Pilot — lib/ Business-Logic Components

    Container_Boundary(lib, "lib/ Business Logic") {
        Component(k8s_client, "k8s_client", "Python (kubernetes SDK)", "Namespaces and Job/Deployment objects targeting InterLink virtual-kubelet nodes")
        Component(helm_client, "helm_client", "Python (helm CLI subprocess)", "helm install / list / get_values / uninstall")
        Component(hpc_client, "hpc_client", "Python (mccli / SSH)", "wstunnel client + supervisord + InterLink plugin lifecycle on the HPC edge-node")
        Component(token_auth, "token_auth", "Python (PyJWT)", "JWT/JWKS validation, namespace derivation, group access checks")
        Component(token_checkin, "token_checkin", "Python (requests)", "EGI Check-in OIDC / token helpers")
        Component(config, "config", "Python (PyYAML)", "Unified pilot_config.yaml loader (site, charts, hpc.nodes)")
        Component(hpc_config, "hpc_config", "Python", "Per-node HPC config resolution from hpc.nodes")
        Component(saved_deployments, "saved_deployments", "Python", "Per-user saved configs (JSON under manager/data) + default-chart seeding")
    }

    Rel(k8s_client, token_auth, "derives namespace")
    Rel(hpc_client, token_auth, "validates token")
    Rel(hpc_client, hpc_config, "resolves node config")
    Rel(helm_client, config, "reads chart catalogue")
    Rel(saved_deployments, config, "seeds default charts")
```

### Component → external system

| Component | Talks to | Via |
|---|---|---|
| `k8s_client` | Kubernetes API | `kubernetes` Python SDK (kubeconfig or in-cluster SA token) |
| `helm_client` | Kubernetes API | `helm` CLI subprocess |
| `hpc_client` | HPC edge-node | `mccli` CLI (SSH + OIDC token auth) |
| `token_auth` / `token_checkin` | EGI Check-in | HTTPS (JWKS + UserInfo endpoints) |
| `config` / `hpc_config` | local filesystem | `pilot_config.yaml` |
| `saved_deployments` | local filesystem / PVC | JSON files under `manager/data/` |
