# Architecture

## Overview

HPC Pilot runs as **two cooperating services** (split out of the original
single-process "manager" in the `pilot-*` repository split):

- **pilot-api** (this repository) — the REST API service under `/api`,
  protected by Bearer-token auth. Hosts all business logic:

  - `lib/` — pure-Python business logic (Kubernetes SDK, `helm` CLI
    subprocess, `mccli`/SSH). No Flask dependency.
  - `api/` — thin JSON wrappers over `lib/`, plus public endpoints
    (`GET /api/site`, `POST /api/auth/*`) used by the GUI.

- **pilot-app** ([separate repository](https://github.com/chbrandt/pilot-app))
  — the HTML web GUI under `/`. A pure HTTP client: it never validates
  JWTs locally and never sees the OIDC client secret. All backend calls go
  through `API_BASE_URL` (in-cluster by default).

The API can run **outside** the cluster (local dev / VM, external
kubeconfig) or **inside** the cluster as a Deployment managed by the
[`charts/manager/`](https://github.com/chbrandt/pilot-deploy/tree/main/charts/manager/) Helm chart (in-cluster ServiceAccount
token). In both cases it speaks to the Kubernetes API and the `helm` CLI; the
[pilot-deploy](https://github.com/chbrandt/pilot-deploy) chart runs both services and wires `API_BASE_URL`.

```
┌─────────────────────────────────────────────────────────────────┐
│                        User's Browser                           │
└────────────────────────────┬────────────────────────────────────┘
                             │  HTTPS /
┌────────────────────────────▼────────────────────────────────────┐
│              Pilot App — pilot-app (GUI service)                 │
│  Jinja templates + session; zero JWT / K8s logic                │
└────────────────────────────┬────────────────────────────────────┘
                             │  HTTP (API_BASE_URL), Bearer token
┌────────────────────────────▼────────────────────────────────────┐
│              Pilot API — server/main.py (this repo)             │
│  /api/* JSON  ·  /api/docs (Swagger)  ·  public /api/site,       │
│  /api/auth/verify, /api/auth/oidc/exchange                      │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                        lib/                               │   │
│  │  ┌────────────┐  ┌─────────────┐  ┌──────────────────┐   │   │
│  │  │ k8s_client │  │ helm_client │  │   hpc_client     │   │   │
│  │  │ K8s SDK    │  │ helm CLI    │  │  mccli / SSH     │   │   │
│  │  └─────┬──────┘  └──────┬──────┘  └────────┬─────────┘   │   │
│  └────────┼─────────────────┼───────────────────┼─────────────┘   │
└───────────┼─────────────────┼───────────────────┼─────────────────┘
            │                 │                   │
            │ K8s API          │ K8s API           │ SSH (mccli)
            │ (kubeconfig      │ (kubeconfig       │ + EGI token
            │  or in-cluster)  │  via helm)        │
            ▼                  ▼                   ▼
   ┌──────────────────┐  ┌─────────────────┐  ┌────────────────┐
   │  EGI Check-in    │  │ Kubernetes      │  │  HPC edge-node │
   │  JWKS / UserInfo │  │ user-<hash> ns  │  │  wstunnel+plugin│
   └──────────────────┘  │  + Helm releases│  └────────────────┘
                         └─────────────────┘
```

---

## Module Responsibilities

### `main.py`
Flask application factory (`create_app`). Registers the API blueprints,
mounts the Swagger UI at `/api/docs`, serves `/health`, and redirects `/`
to the docs.

### `lib/k8s_client.py`
Wraps the official `kubernetes` Python SDK. Manages namespaces and job
(`Deployment`) objects targeting InterLink virtual-kubelet nodes. See
[kubernetes.md](kubernetes.md).

### `lib/helm_client.py`
Wraps the `helm` CLI via `subprocess.run()`. Functions: `helm_install`,
`helm_list`, `helm_get_values`, `helm_uninstall`. See [helm.md](helm.md).

### `lib/hpc_client.py`
Wraps `mccli` (motley-cue SSH client) to install and manage the wstunnel client
+ supervisord + InterLink plugin on a remote HPC node. See [lib.md](lib.md).

### `lib/config.py`
Unified configuration loader: parses `server/pilot_config.yaml` (or a
`--config`/`PILOT_CONFIG_PATH` override) and exposes its `site`, `charts`
and `hpc.nodes` sections.

### `lib/hpc_config.py`
Loads per-node HPC configs from the `hpc.nodes` section via `lib/config.py`.

### `lib/token_auth.py`
EGI Check-in JWT/JWKS validation, namespace derivation, UserInfo-based group
access checks. See [authentication.md](authentication.md).

### `lib/saved_deployments.py`
Per-user saved-configuration store (JSON files under `server/data/`), plus
the default-chart seeding logic driven by the `charts` section of
`pilot_config.yaml`.

### `api/` layer
Thin JSON wrappers over `lib/`. Each module is a Flask blueprint with the
`/api` prefix. Auth is enforced by `require_token` (`api/auth.py`).

### `app/` layer (now pilot-app)
The HTML GUI has moved to the
[pilot-app repository](https://github.com/chbrandt/pilot-app) as a separate
service. Its backend calls go through `app/api_client.py`
(`api_get`/`api_post`/`api_delete`) pointing at `API_BASE_URL`; login uses the
public `POST /api/auth/verify` and `POST /api/auth/oidc/exchange` endpoints,
so it has no JWT logic and no OIDC secret.

---

## Request Lifecycle — Job Submission

```
Browser            app/ (k8s_bp)        api_client          api/ (k8s_bp)        lib/k8s_client      K8s API
   │  POST /submit    │                    │                   │                    │                  │
   │─────────────────►│ validate form       │                   │                    │                  │
   │                  │ api_post /api/jobs  │                   │                    │                  │
   │                  │───────────────────► │ POST /api/jobs/preset│                    │                  │
   │                  │                    │──────────────────►│ require_token      │                  │
   │                  │                    │                   │ derive namespace   │                  │
   │                  │                    │                   │ create_job(...)   │                  │
   │                  │                    │                   │──────────────────► │ POST Deployment  │
   │                  │                    │                   │                    │ (nodeSelector +  │
   │                  │                    │                   │                    │  toleration)     │
   │                  │                    │                   │◄────────────────── │ 201              │
   │                  │                    │◄──────────────────│                    │                  │
   │ render status    │◄────────────────── │                   │                    │                  │
   │◄─────────────────│                    │                   │                    │                  │
   │  (status.html polls GET /jobs/<name>/status until "succeeded"/"failed")            │                  │
```

The submitted `Deployment` is pinned to an InterLink virtual-kubelet node;
InterLink then forwards the pod to an HPC batch job on the connected site
(once the HPC edge-node side is wired up via wstunnel).

---

## Request Lifecycle — InterLink Install

```
Browser            app/ (helm_bp)       api_client          api/ (helm_bp)       lib/helm_client     helm CLI      K8s API
   │  POST /helm/install │                 │                   │                    │                  │             │
   │────────────────────►│ api_post        │                   │                    │                  │             │
   │                     │ /api/interlink  │                   │                    │                  │             │
   │                     │────────────────►│ POST /api/interlink│                   │                  │             │
   │                     │                 │──────────────────►│ require_token      │                  │             │
   │                     │                 │                   │ resolve placeholders│                 │             │
   │                     │                 │                   │ helm_install(...)  │                  │             │
   │                     │                 │                   │──────────────────►│ helm install     │             │
   │                     │                 │                   │                    │ --wait (≤5min)   │ apply        │
   │                     │                 │                   │                    │─────────────────►│────────────►│
   │                     │                 │                   │◄──────────────────│                  │             │
   │ render helm_result  │◄────────────────│◄─────────────────│                    │                  │             │
   │◄────────────────────│                 │                   │                    │                  │             │
```

`POST /api/interlink` reads the InterLink chart reference, version and default
values from the `charts` section of `pilot_config.yaml`, resolves
`__NAMESPACE__`/`__HOSTNAME__`, and runs `helm install` into the user's
namespace.

---


## Request Lifecycle — HPC Deploy

```
Browser      app/ (hpc_bp)    api_client      api/ (hpc_bp)         lib/hpc_client        mccli/SSH         HPC node
   │ POST /hpc/deploy │            │                │                     │                   │                │
   │─────────────────►│ api_post   │                │                     │                   │                │
   │                  │ /api/hpc/deploy             │                     │                   │                │
   │                  │───────────►│ POST /api/hpc/deploy                │                   │                │
   │                  │            │────────────────►│ require_token      │                   │                │
   │                  │            │                │ resolve hpc_name →  │                   │                │
   │                  │            │                │ load_hpc_config     │                   │                │
   │                  │            │                │ compute wstunnel    │                   │                │
   │                  │            │                │ hpc_client.deploy() │                   │                │
   │                  │            │                │────────────────────►│ step functions    │                │
   │                  │            │                │                     │ (mkdir, venv,     │                │
   │                  │            │                │                     │  pip supervisor,  │                │
   │                  │            │                │                     │  wstunnel dl,     │                │
   │                  │            │                │                     │  plugin install,  │                │
   │                  │            │                │                     │  start supervisord)               │
   │                  │            │                │                     │──────────────────►│──────────────►│
   │                  │            │                │◄────────────────────│                   │                │
   │ render hpc_result│◄───────────│◄────────────────│                   │                   │                │
   │◄─────────────────│            │                │                     │                   │                │
```

The wstunnel client connects back to the in-cluster InterLink wstunnel server
using path-prefix routing on the shared `site_config.hostname`
(`--http-upgrade-path-prefix <namespace>`).

---

## Template Map

```
base.html  (navbar, flash messages, token-countdown JS)
  ├── login.html        → POST /login
  ├── index.html        → POST /submit             → status.html
  ├── nodes.html         → POST /hpc/{deploy,status,start,stop}     → hpc_result.html
  │                       POST /hpc/nodes/interlink/{deploy,delete}
  ├── deployments.html  → (unified workloads view: jobs + interlink)
  │                       GET  /jobs/<ns>/<name>/output → output.html
  │                       POST /jobs/<ns>/<name>/delete
  │                       POST /hpc/nodes/interlink/delete
  └── output.html       → (job stdout/stderr)     → GET /jobs/<ns>/<name>/output
```

> `pods.html` and `container.html` are legacy templates kept in the tree but
> not referenced by any current route.

---

## Session Data

The Flask session (encrypted client-side cookie, signed with
`FLASK_SECRET_KEY`) stores:

| Key | Type | Description |
|---|---|---|
| `token` | `str` | Raw JWT access token (forwarded as Bearer token to the REST API) |
| `claims` | `dict` | Decoded JWT claims (`sub`, `exp`, `iss`, …) |
| `namespace` | `str` | User's Kubernetes namespace (derived from `sub`) |

---

## Security Notes

- The app never stores credentials server-side; state lives in the encrypted
  client cookie.
- Namespace isolation is enforced server-side: GUI delete/save routes check that
  the requested namespace matches `session["namespace"]`; the REST API derives
  the namespace from the token and never trusts a client-supplied namespace.
- JWKS keys are fetched over HTTPS and cached (1-hour TTL); key rotation is
  handled by retrying on a cache miss.
- All Helm operations are scoped to the user's namespace via `--namespace`.
- Optional `allowed_groups` in `site_config.yaml` restricts access to members
  of specific EGI VOs (verified via the UserInfo endpoint — see
  [authentication.md](authentication.md)).

