# Technical FAQ

## How do I set up my development environment?
1. Clone the main repository from GitHub
2. Install Docker Desktop (version 4.0 or later)
3. Run `docker compose up` to start all services
4. Access the dev portal at http://localhost:3000
5. Use your SSO credentials to log in

## What is our tech stack?
- Frontend: React 18 with TypeScript
- Backend: Python (FastAPI) and Go microservices
- Database: PostgreSQL 15 for relational data, Redis for caching
- Message Queue: RabbitMQ
- CI/CD: GitHub Actions with ArgoCD for deployments
- Cloud: AWS (EKS, RDS, S3, CloudFront)

## How do I deploy to staging?
Push your branch and create a PR. Once approved and merged to `develop`, GitHub Actions automatically deploys to staging. Monitor the deployment in the #deploys Slack channel.

## How do I get access to production logs?
Request access through the IT portal under "Production Access." Requires manager approval. Once granted, use `kubectl logs` with the production kubeconfig or check Grafana dashboards.

## What is the incident response process?
1. If you detect an issue, check the #incidents Slack channel first
2. If no existing incident, create one using the /incident Slack command
3. Assign severity: P1 (service down), P2 (degraded), P3 (minor impact)
4. P1 incidents require immediate page to on-call engineer
5. Post-mortem is required for all P1 and P2 incidents within 48 hours

## How do I request a new API key?
Submit a request through the developer portal. API keys are scoped to specific services. Production keys require security team review (allow 2 business days).
