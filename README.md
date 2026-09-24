# DevPulse — a self-hosted uptime monitor, deployed the way you'd deploy anything else

## The theme, in one line

Every DevOps team ends up building a small internal tool to watch the health
of the services it owns — an "UptimeRobot" you run yourself instead of
paying for. **DevPulse is that tool.** It's a single Python service that
pings a list of URLs on a schedule, records the results in Postgres, and
exposes Prometheus metrics — and it is deployed with the exact same
production pipeline you'd use for any other service: Docker → Terraform →
GKE → GitHub Actions with keyless OIDC auth → Prometheus/Grafana. It eats
its own dog food: the tool that watches your other services is deployed,
monitored, and secured the same way they are.

## What it actually does

- `POST /targets` — register a URL to watch, with a friendly name
- `GET /targets` — list watched URLs with their most recent check result
- A background scheduler pings every registered target every 30s (default),
  storing status code, latency, and up/down in Postgres
- `GET /metrics` — Prometheus exposition format: `devpulse_target_up`,
  `devpulse_target_latency_seconds`, `devpulse_checks_total`,
  `devpulse_check_failures_total`
- `GET /healthz` / `GET /readyz` — Kubernetes probes

## Architecture

**CI (build-time):** GitHub → GitHub Actions, authenticating to GCP via
**Workload Identity Federation** (OIDC — no downloaded service-account key,
ever) → lint → **SAST** (CodeQL) → **SCA** (`pip-audit`) → **secrets scan**
(gitleaks) → **IaC scan** (`trivy config`) → Docker build → **image scan**
(Trivy) → push to Artifact Registry.

**IaC:** Terraform, GCS backend with state locking, modules for VPC
(private subnet + Cloud NAT), GKE Autopilot, Artifact Registry, Cloud SQL
(private IP, automated + point-in-time-recovery backups), and the WIF
pool/service account.

**CD (deploy-time):** on a successful CI run on `main`, GitHub Actions
authenticates with the same OIDC identity and applies the Kubernetes
manifests to GKE via Kustomize.

**Runtime:** GKE Autopilot, a Deployment with 2 replicas, resource
requests/limits, liveness/readiness probes, HPA (2–6 replicas on CPU),
NetworkPolicy (default-deny + explicit allow rules), Ingress + cert-manager
for TLS, DB credentials from Secret Manager.

**Observability:** `kube-prometheus-stack` (Prometheus + Grafana +
Alertmanager) via Helm. A `ServiceMonitor` scrapes DevPulse's own `/metrics`
endpoint every 30s. Alerts fire on: the DevPulse pod itself crash-looping,
one of DevPulse's own watched targets going down for 5+ minutes, or the HPA
sitting maxed out for 10+ minutes.

## Repo layout

```
devpulse/
├── app/                    main.py, init.sql, requirements.txt, Dockerfile
├── docker-compose.yml      local dev — app + Postgres on your laptop
├── terraform/
│   ├── modules/            vpc, gke, artifact-registry, cloudsql, iam-wif
│   └── envs/dev/           root module wiring the above together
├── k8s/
│   ├── base/                deployment, ingress, hpa, network-policy, kustomization
│   └── overlays/dev/       image tag + namespace + replica overrides
├── .github/workflows/      ci.yml, cd.yml
├── monitoring/             prometheus-values.yaml, servicemonitor.yaml, alert-rules.yaml
└── .gitleaks.toml, .gitignore, .dockerignore
```

---

## Fixes made for smooth, reliable demo execution

These were found and corrected specifically so a live run doesn't stumble:

| Issue | Fix |
|---|---|
| `psycopg2-binary==2.9.9` predates Python 3.14 support (added in `2.9.11`) — no prebuilt wheel exists for 3.14, so `pip install` inside the Docker build would try to compile from source and fail without build tools present. | Bumped to `psycopg2-binary==2.9.12`, which ships a Python 3.14 wheel. |
| `@app.on_event("startup"/"shutdown")` is FastAPI's deprecated event-hook style — it still works but throws deprecation noise and is being phased out. | Rewrote `main.py` to use the modern `lifespan` context manager. |
| In `docker-compose`, Postgres reports "started" a couple of seconds before it actually accepts connections — the app container could crash on its very first boot before settling on retry. | Added a `pg_isready` healthcheck to the `db` service and `condition: service_healthy` on `devpulse`, plus a `wait_for_db()` retry loop in the app itself as a second layer of defense. |

## Prerequisites (Windows / PowerShell)

- Docker Desktop (with the WSL2 backend enabled)
- `gcloud`, `terraform` (>=1.9), `kubectl`, `kustomize`, `helm` — install via
  their official Windows installers, or `winget`/`choco`/`scoop`, and confirm
  each is on your `PATH`:
  ```powershell
  gcloud --version
  terraform --version
  kubectl version --client
  helm version
  ```
- Python 3.14 (only needed locally if you want to run `main.py` outside
  Docker — the container build doesn't need it on your machine)
- A GCP project with billing enabled, and a GitHub repo you own with this
  code pushed to it

All commands below are native PowerShell — no WSL or Git Bash required.
`gcloud`, `terraform`, `kubectl`, and `helm` are plain executables and behave
identically in PowerShell.

---

## Step-by-step execution

### Step 1 — Run it locally first
```powershell
docker compose up --build
```
In a second PowerShell window:
```powershell
Invoke-RestMethod -Uri http://localhost:8000/targets -Method Post `
  -ContentType "application/json" `
  -Body '{"name": "google", "url": "https://google.com"}'

Invoke-RestMethod -Uri http://localhost:8000/targets
Invoke-RestMethod -Uri http://localhost:8000/metrics
```
Confirm a target shows `is_up: True` after ~30 seconds. This proves the app
works before any cloud infra enters the picture.

### Step 2 — Enable required GCP APIs
```powershell
gcloud config set project YOUR_PROJECT_ID
gcloud services enable `
  container.googleapis.com `
  sqladmin.googleapis.com `
  artifactregistry.googleapis.com `
  iam.googleapis.com `
  iamcredentials.googleapis.com `
  servicenetworking.googleapis.com `
  secretmanager.googleapis.com `
  cloudresourcemanager.googleapis.com
```
(The backtick `` ` `` is PowerShell's line-continuation character — equivalent to `\` in bash.)

### Step 3 — Create the Terraform state bucket (once, manually)
```powershell
gsutil mb -l us-central1 gs://YOUR_PROJECT_ID-tfstate
gsutil versioning set on gs://YOUR_PROJECT_ID-tfstate
```
Edit `terraform/envs/dev/backend.tf` and replace
`REPLACE_WITH_YOUR_TFSTATE_BUCKET` with that bucket name.

### Step 4 — Configure Terraform variables
```powershell
cd terraform/envs/dev
Copy-Item terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars   # set project_id, region, github_repo
```

### Step 5 — Provision infrastructure
```powershell
terraform init
terraform plan -out=tfplan
terraform apply tfplan
terraform output
```
Creates: VPC + private subnet + NAT, GKE Autopilot cluster, Artifact
Registry, Cloud SQL (private IP, backed up), and the WIF pool + scoped
service account.

### Step 6 — Load the database schema
```powershell
$connName = terraform output -raw cloudsql_connection_name
$instance = ($connName -split ":")[2]
Get-Content ..\..\..\app\init.sql | gcloud sql connect $instance --user=devpulse --database=devpulse
```
(Password is in Secret Manager, under the secret name from `terraform output`.)

### Step 7 — Configure GitHub repo variables (no secrets/keys needed)
GitHub → Settings → Secrets and variables → Actions → **Variables** tab:

| Variable | Value |
|---|---|
| `GCP_PROJECT_ID` | your project id |
| `GCP_REGION` | e.g. `us-central1` |
| `GKE_CLUSTER_NAME` | from `terraform output gke_cluster_name` |
| `WORKLOAD_IDENTITY_PROVIDER` | from `terraform output workload_identity_provider` |
| `CI_SERVICE_ACCOUNT_EMAIL` | from `terraform output ci_service_account_email` |

No `GCP_SA_KEY` secret exists anywhere — that's the point of Step 5's WIF setup.

### Step 8 — Push to trigger CI
```powershell
git add .
git commit -m "initial commit"
git push origin main
```
Watch the **Actions** tab: lint → CodeQL → `pip-audit` → gitleaks →
`trivy config` → Docker build → Trivy image scan → push to Artifact
Registry.

### Step 9 — Bootstrap the cluster namespace and secret (once)
```powershell
kubectl create namespace devpulse-dev

$dbIp = terraform output -raw cloudsql_private_ip
$dbPass = gcloud secrets versions access latest --secret=devpulse-db-password

kubectl create secret generic db-credentials -n devpulse-dev `
  --from-literal=DB_HOST=$dbIp `
  --from-literal=DB_NAME=devpulse `
  --from-literal=DB_USER=devpulse `
  --from-literal=DB_PASS=$dbPass
```

### Step 10 — CD deploys automatically
On a successful CI run on `main`, `cd.yml` authenticates via the same WIF
identity, fetches GKE credentials, and runs `kubectl apply -k k8s/overlays/dev`.
Nothing to run locally for this step.

### Step 11 — Verify
```powershell
kubectl get pods -n devpulse-dev
kubectl get svc -n devpulse-dev
kubectl get hpa -n devpulse-dev
```

### Step 12 — Install monitoring
```powershell
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install prometheus prometheus-community/kube-prometheus-stack `
  -n monitoring --create-namespace -f monitoring/prometheus-values.yaml

kubectl apply -f monitoring/servicemonitor.yaml
kubectl apply -f monitoring/alert-rules.yaml
```
Access Grafana:
```powershell
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# open http://localhost:3000 — admin / (password from prometheus-values.yaml)
```
Build one panel on `devpulse_target_up` and one on
`devpulse_target_latency_seconds` — that's the whole point of the tool,
visualized.

### Step 13 — Expose it (optional, real domain + TLS)
Install `ingress-nginx` and `cert-manager` via Helm, point DNS at the
ingress IP, then edit the hostname in `k8s/base/ingress.yaml`.

### Step 14 — Prove the rollback path
```powershell
kubectl rollout undo deployment/devpulse -n devpulse-dev
kubectl rollout status deployment/devpulse -n devpulse-dev
```
Do this once, deliberately, so it's tested — not assumed.

---

## Versions used, and why (checked against current releases at time of writing)

| Component | Pinned to | Why |
|---|---|---|
| Python | `3.14` | Matches local dev version. |
| `psycopg2-binary` | `2.9.12` | `2.9.9` has no Python 3.14 wheel — this is the one that actually breaks the build if left unpinned upward. |
| `hashicorp/google` provider | `~> 8.0` | Current major — has breaking changes vs older v5 pins, review before applying to existing state. |
| Cloud SQL | `POSTGRES_17` | Latest GA on Cloud SQL at time of writing. |
| `actions/checkout` / `setup-python` | `@v7` / `@v6` | Older majors stopped working once GitHub removed Node 20 runners (Sept 16, 2026). |
| `google-github-actions/*` | `@v3` | Current major, Node 24-compatible. |
| `github/codeql-action` | `@v4` | Current major. |
| `gitleaks/gitleaks-action` | `@v3` | v2 is dead post-Node-20 removal. |
| `aquasecurity/trivy-action` | `@0.35.0` | First tag confirmed safe after the March 2026 supply-chain compromise of tags `0.0.1`–`0.34.2`. Pin to a commit SHA for real production use. |
| `tfsec-action` | removed, replaced with `trivy config` | tfsec is unmaintained; its checks were merged into Trivy. |

## What's intentionally left as a next step
- External Secrets Operator instead of the manual `kubectl create secret` in Step 9
- ArgoCD/GitOps instead of `kubectl apply` from CI
- OPA/Gatekeeper policies (deny `:latest` tags, require resource limits)
- Multi-target alert routing (per-target Slack channel instead of one global one)
- Multi-environment promotion (dev → staging → prod) via `k8s/overlays/`
