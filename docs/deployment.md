# Deployment Guide

This guide covers deploying the full HPC Pilot stack in a Kubernetes
cluster: the **Pilot API** and **Pilot App** services, the per-user
**InterLink pods**, and the **HPC edge-node** wstunnel client that
connects them. All Helm charts live in the
[pilot-deploy](https://github.com/chbrandt/pilot-deploy) repository.

## Architecture overview (in-cluster)

```
                ┌─────────────────────────────────────────────────┐
                │            Kubernetes Cluster                   │
                │  Namespace: hpc-pilot                           │
                │  ┌────────────────────┐   ┌──────────────────┐ │
   Browser ─────┼─►│ Deployment:        │──►│ Deployment:       │ │
   (HTTPS)      │  │  pilot-app (GUI)   │   │  pilot-api        │ │
                │  │  Ingress: "/"      │   │  Ingress: "/api"  │ │
   curl ────────┼──────────────────────────────► (Bearer token) │ │
                │  └────────────────────┘   └────────┬─────────┘ │
                │                                     │ helm install
                │                                     ▼ interlink (per user)
                │  Namespace: user-<hash>                         │
                │  Pod: vk-node-<hpc>-<hash>                     │
                │    ├── interLink API server (port 3000)         │
                │    └── wstunnel server    (port 8080)           │
                │  Ingress: <hostname>/<namespace> (path)         │
                └─────────────────────────────────────────────────┘
```

> Routing is **path-prefix** on a single `hostname`: each user's wstunnel is
> reached at `https://<hostname>/<namespace>`. **No wildcard DNS or wildcard
> TLS certificate is required.**

## Prerequisites

| Requirement | Notes |
|---|---|
| Kubernetes ≥ 1.24 | Any distribution (minikube, k3s, EKS, GKE, …) |
| Helm v3 | `brew install helm` or `snap install helm --classic` |
| nginx Ingress controller | `helm install ingress-nginx ingress-nginx/ingress-nginx` |
| A DNS record | `<hostname>` → Ingress controller external IP (single host) |
| A TLS certificate | for `<hostname>` (cert-manager + Let's Encrypt, or pre-existing) |
| Container registry | for the `pilot-api` and `pilot-app` images |

## Step 1 — Build and push the images

```bash
# pilot-api (this repository)
docker build -t ghcr.io/<your-org>/pilot-api:latest .
docker push ghcr.io/<your-org>/pilot-api:latest

# pilot-app (separate repository)
git clone https://github.com/chbrandt/pilot-app && cd pilot-app
docker build -t ghcr.io/<your-org>/pilot-app:latest .
docker push ghcr.io/<your-org>/pilot-app:latest
```

Both images are `python:3.11-slim` based. The **pilot-api** image also
bundles the `helm` CLI, `openssh-client` and `mccli` (needed for
InterLink chart installs and HPC edge-node operations).

## Step 2 — Configure DNS and TLS

Point a single hostname (e.g. `hpc-pilot.example.com`) at the nginx Ingress
controller's external IP and provision a TLS certificate for it.

```yaml
ingress:
  className: nginx
  tls:
    enabled: true
    secretName: pilot-tls
```

No wildcard record or wildcard certificate is needed.

## Step 3 — Install the Helm chart (pilot-deploy)

```bash
API_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))')
APP_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))')

git clone https://github.com/chbrandt/pilot-deploy && cd pilot-deploy

helm install pilot ./charts/manager \
  --namespace hpc-pilot --create-namespace \
  --set api.image.repository=ghcr.io/<your-org>/pilot-api \
  --set api.image.tag=latest \
  --set api.flask.secretKey="${API_SECRET}" \
  --set app.image.repository=ghcr.io/<your-org>/pilot-app \
  --set app.image.tag=latest \
  --set app.flask.secretKey="${APP_SECRET}" \
  --set siteConfig.hostname=hpc-pilot.example.com \
  --set interlinkConfig.chart=oci://ghcr.io/chbrandt/interlink-helm-chart/interlink
```

Resources created:

| Resource | (default) name | Purpose |
|---|---|---|
| Namespace | `hpc-pilot` | Dedicated pilot namespace |
| ServiceAccount + RBAC | `<ns>-sa` + ClusterRole | In-cluster identity for the API (K8s + Helm ops) |
| ConfigMap | `<release>-pilot-config` | `pilot_config.yaml` (site + charts + hpc config) |
| Secrets | `<release>`, `<release>-app` | `FLASK_SECRET_KEY` for each service |
| Deployments | `pilot-api`, `pilot-app` | The two services |
| Services | `pilot-api`, `pilot-app` | ClusterIP → Flask ports |
| Ingress | `<release>` | `/` → app service, `/api` → api service |
| PVC | `<release>-data` (optional) | `/app/data` — durable saved-config store |

> The GUI pod reaches the API in-cluster via `API_BASE_URL` (derived from
> the api Service name; override with `app.apiBaseUrl` when needed). The
> OIDC client secret is injected into the **API** pod only, via
> `PILOT_OIDC_CLIENT_SECRET`.

## Step 4 — Verify

```bash
kubectl -n hpc-pilot get pods,svc,ingress

# Both services must answer their public health endpoints:
kubectl -n hpc-pilot port-forward svc/pilot-api 5000:80 &
curl http://localhost:5000/health
kubectl -n hpc-pilot port-forward svc/pilot-app 5001:80 &
curl http://localhost:5001/health
```

## Step 5 — Connect an HPC edge-node

Configure the HPC nodes under `hpcConfig.nodes` (see
[Configuration](configuration.md)), then use the GUI's **Manage Nodes**
page or call the API directly:

```bash
curl -X POST https://<hostname>/api/hpc/deploy \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"hpc_name": "my-cluster"}'
```

The call installs wstunnel, supervisord and the InterLink plugin on the
remote node via `mccli`/SSH and starts
`wstunnel client --http-upgrade-path-prefix <namespace> …`.

For the complete flow see [Architecture](architecture.md) and
[Authentication](authentication.md).
