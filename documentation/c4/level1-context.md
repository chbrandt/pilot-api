# Level 1 — System Context

**Question:** what does HPC Pilot do, and which people/systems does it interact with?

HPC Pilot sits between an EGI community user, the EGI Check-in identity
provider, a Kubernetes cluster (cloud), and an HPC cluster (batch systems). It
turns user-submitted container workloads into HPC batch jobs, routing them
through per-user InterLink pods that tunnel back to the HPC edge-node.

```mermaid
C4Context
    title HPC Pilot — System Context (Level 1)

    Person(user, "Researcher / Operator", "EGI community member using a web browser")

    System(pilot, "HPC Pilot", "Manages cloud-native jobs on HPC appliances for EGI communities")

    System_Ext(checkin, "EGI Check-in", "OIDC / OAuth2 identity provider (authentication & authorization)")
    System_Ext(k8s, "Kubernetes Cluster", "Cloud platform that runs the manager and per-user InterLink pods")
    System_Ext(hpc, "HPC Cluster", "Edge-nodes and batch systems (Slurm / Docker) where jobs actually run")

    Rel(user, pilot, "Submits jobs, deploys InterLink pods, manages HPC nodes", "HTTPS")
    Rel(user, checkin, "Authenticates (OAuth2 browser login or token paste)", "HTTPS")
    Rel(pilot, checkin, "Validates JWT, fetches JWKS / UserInfo", "HTTPS")
    Rel(pilot, k8s, "Creates namespaces, deploys InterLink pods and workloads", "K8s API / Helm CLI")
    Rel(pilot, hpc, "Installs and manages wstunnel client + InterLink plugin", "SSH (mccli)")
    Rel(k8s, hpc, "Forwards pods to batch jobs (InterLink API server ↔ plugin)", "WebSocket (wstunnel)")
```

## Elements

| Element | Type | Role |
|---|---|---|
| Researcher / Operator | Person | Submits container jobs and manages their HPC environment through the web UI |
| HPC Pilot | System (this system) | The Flask manager + per-user InterLink pods + HPC edge agents |
| EGI Check-in | External system | Authenticates users and issues JWTs; authorizes via group entitlements |
| Kubernetes Cluster | External system | Runs the manager and the per-user InterLink pods (virtual-kubelets) |
| HPC Cluster | External system | Hosts the edge-node agents and the actual batch jobs |
