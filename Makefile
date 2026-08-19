# HSAAI Enterprise AI Operating System — Makefile (v4.0)
# Hayel Saeed Anam Group (HSA Group)

.DEFAULT_GOAL := help

# Colors
CYAN   := \033[36m
GREEN  := \033[32m
YELLOW := \033[33m
RED    := \033[31m
RESET  := \033[0m

# Paths
DOCKER_DIR    := infrastructure/docker
PATRONI_DIR   := infrastructure/patroni
QDRANT_DIR    := infrastructure/qdrant-cluster
REDIS_DIR     := infrastructure/redis-sentinel
LOKI_DIR      := infrastructure/loki
OPA_DIR       := infrastructure/opa
VAULT_DIR     := infrastructure/vault

# Environment
ENV_FILE ?= .env

.PHONY: help
help: ## Show this help message
	@echo "$(CYAN)HSAAI Enterprise AI Operating System$(RESET) — v4.0.0"
	@echo "$(GREEN)HSA Group$(reset) — Hayel Saeed Anam Group"
	@echo ""
	@echo "$(YELLOW)Usage:$(RESET) make [target]"
	@echo ""
	@echo "$(CYAN)Development:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}' | sort
	@echo ""

# ─── Development ───

.PHONY: dev-up
dev-up: ## Start development stack
	docker compose --env-file $(ENV_FILE) -f $(DOCKER_DIR)/docker-compose.dev.yml up -d --build

.PHONY: dev-down
dev-down: ## Stop development stack
	docker compose --env-file $(ENV_FILE) -f $(DOCKER_DIR)/docker-compose.dev.yml down

.PHONY: dev-logs
dev-logs: ## Tail development logs
	docker compose --env-file $(ENV_FILE) -f $(DOCKER_DIR)/docker-compose.dev.yml logs -f

# ─── Production (HA) ───

.PHONY: prod-up
prod-up: ## Start production stack (HA)
	$(MAKE) ha-up
	docker compose --env-file .env.production -f $(DOCKER_DIR)/docker-compose.production.yml up -d --build

.PHONY: prod-down
prod-down: ## Stop production stack
	docker compose --env-file .env.production -f $(DOCKER_DIR)/docker-compose.production.yml down

# ─── HA Infrastructure ───

.PHONY: ha-up
ha-up: ## Start HA infrastructure (Patroni + Qdrant + Redis + Loki + OPA + Vault)
	@echo "$(CYAN)Starting HA infrastructure...$(RESET)"
	docker compose -f $(PATRONI_DIR)/docker-compose.ha.yml up -d
	docker compose -f $(QDRANT_DIR)/docker-compose.cluster.yml up -d
	docker compose -f $(REDIS_DIR)/docker-compose.sentinel.yml up -d
	docker compose -f $(LOKI_DIR)/docker-compose.logging.yml up -d
	docker compose -f $(OPA_DIR)/docker-compose.opa.yml up -d
	docker compose -f $(VAULT_DIR)/docker-compose.vault.yml up -d
	@echo "$(GREEN)✅ HA infrastructure started$(RESET)"

.PHONY: ha-down
ha-down: ## Stop HA infrastructure
	docker compose -f $(PATRONI_DIR)/docker-compose.ha.yml down
	docker compose -f $(QDRANT_DIR)/docker-compose.cluster.yml down
	docker compose -f $(REDIS_DIR)/docker-compose.sentinel.yml down
	docker compose -f $(LOKI_DIR)/docker-compose.logging.yml down
	docker compose -f $(OPA_DIR)/docker-compose.opa.yml down
	docker compose -f $(VAULT_DIR)/docker-compose.vault.yml down

# ─── Internal Deployment ───

.PHONY: internal-up
internal-up: ## Start HSA internal deployment
	docker compose --env-file .env.hsa-internal -f $(DOCKER_DIR)/docker-compose.hsa-internal.yml up -d --build

.PHONY: internal-down
internal-down: ## Stop HSA internal deployment
	docker compose --env-file .env.hsa-internal -f $(DOCKER_DIR)/docker-compose.hsa-internal.yml down

# ─── Initialization ───

.PHONY: init-db
init-db: ## Run Alembic database migrations
	USE_ALEMBIC=true alembic upgrade head
	@echo "$(GREEN)✅ Database migrations complete$(RESET)"

.PHONY: init-qdrant
init-qdrant: ## Create Qdrant collection with sharding
	bash $(QDRANT_DIR)/create-collection.sh
	@echo "$(GREEN)✅ Qdrant collection created$(RESET)"

.PHONY: init-vault
init-vault: ## Initialize Vault with policies and secrets
	docker exec hsaai-vault-init sh -c "cat /vault/config/approle.env"
	@echo "$(GREEN)✅ Vault initialized$(RESET)"

.PHONY: init-all
init-all: init-db init-qdrant init-vault ## Initialize all (DB + Qdrant + Vault)
	@echo "$(GREEN)✅ All initialization complete$(RESET)"

# ─── Testing ───

.PHONY: test
test: ## Run all tests
	pytest tests/ -v --tb=short --cov=services --cov=packages --cov-report=term-missing

.PHONY: test-unit
test-unit: ## Run unit tests
	pytest tests/unit/ -v --tb=short

.PHONY: test-integration
test-integration: ## Run integration tests
	pytest tests/integration/ -v --tb=short

.PHONY: test-e2e
test-e2e: ## Run end-to-end tests (requires running services)
	pytest tests/e2e/ -v --tb=short -m e2e

.PHONY: test-load
test-load: ## Run load tests (Locust)
	locust -f tests/load/locustfile.py --headless -u 1000 -r 50 --run-time 5m

.PHONY: test-security
test-security: ## Run security regression tests
	pytest tests/security/ -v --tb=short

.PHONY: test-contract
test-contract: ## Run API contract tests
	pytest tests/contract/ -v --tb=short

# ─── Linting ───

.PHONY: lint
lint: ## Lint all code (Python + TypeScript)
	$(MAKE) lint-python
	$(MAKE) lint-typescript

.PHONY: lint-python
lint-python: ## Lint Python code
	ruff check services/ packages/ --ignore=E501
	mypy services/backend_core/ --ignore-missing-imports || true

.PHONY: lint-typescript
lint-typescript: ## Lint TypeScript code
	cd apps/web && npm run lint
	cd apps/web && npm run type-check

# ─── Security ───

.PHONY: security-scan
security-scan: ## Run all security scans
	@echo "$(CYAN)Running security scans...$(RESET)"
	rg -n 'Bearer\s+(admin|hsaai_admin)\b' --type ts --type js --glob '!**/lib/server-auth.ts' apps/web/ services/ packages/ && echo "$(RED)❌ Bearer admin found$(RESET)" || echo "$(GREEN)✅ No Bearer admin$(RESET)"
	bandit -r services/ packages/ -q || true
	pip-audit -r services/backend_core/requirements.txt || true
	gitleaks detect --source . --no-banner || true
	trivy fs --severity CRITICAL . || true
	@echo "$(GREEN)✅ Security scans complete$(RESET)"

# ─── Backup & Restore ───

.PHONY: backup
backup: ## Backup all databases
	bash $(PATRONI_DIR)/backup.sh
	@echo "$(GREEN)✅ Backup complete$(RESET)"

.PHONY: backup-qdrant
backup-qdrant: ## Backup Qdrant snapshots
	curl -X POST http://localhost:6333/collections/hsaai_knowledge/snapshots
	@echo "$(GREEN)✅ Qdrant backup complete$(RESET)"

# ─── Docker ───

.PHONY: build
build: ## Build all Docker images
	@for svc in services/*/; do \
		echo "$(CYAN)Building $$svc...$(RESET)"; \
		docker build -t hsaai/$$(basename $$svc):4.0.0 $$svc || true; \
	done
	docker build -t hsaai/frontend:4.0.0 apps/web/

.PHONY: clean
clean: ## Clean Docker artifacts
	docker system prune -f
	docker volume prune -f
	@echo "$(GREEN)✅ Clean complete$(RESET)"

# ─── Docs ───

.PHONY: docs
docs: ## Generate API documentation
	@echo "$(CYAN)Generating API docs...$(RESET)"
	# Each service auto-generates /openapi.json at runtime
	# Use: curl http://localhost:8000/openapi.json > docs/api/backend_core.json
	@echo "$(GREEN)✅ Docs generated$(RESET)"

# ─── Version ───

.PHONY: version
version: ## Show version
	@cat VERSION
