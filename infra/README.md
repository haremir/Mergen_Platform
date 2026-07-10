# infra/

Infrastructure-as-code and deployment configuration for the Mergen Platform.

## Contents (planned)

| Directory            | Purpose                                              |
|----------------------|------------------------------------------------------|
| `docker/`            | Dockerfile and docker-compose definitions            |
| `k8s/`               | Kubernetes manifests (Deployments, Services, etc.)   |
| `terraform/`         | Cloud infrastructure provisioning (GCP/AWS)          |
| `scripts/`           | CI/CD helper scripts, database migration runners     |
| `nginx/`             | Reverse proxy configuration                          |

> **Note**: No Python packages live here — infra is configuration and tooling only.
