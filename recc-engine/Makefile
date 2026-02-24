UV ?= uv

.PHONY: help sync sync-dev lock run migrate-users docker-build docker-up docker-down docker-logs test test-backend test-routes test-syntax

help:
	@echo "Available targets:"
	@echo "  make sync         - Install runtime dependencies via uv"
	@echo "  make sync-dev     - Install runtime + dev/test dependencies via uv"
	@echo "  make lock         - Refresh uv.lock"
	@echo "  make run          - Run API server with uv"
	@echo "  make migrate-users - Migrate legacy users/*.json profiles to SQLite"
	@echo "  make docker-build - Build Docker image via docker compose"
	@echo "  make docker-up    - Start API container with mounted state"
	@echo "  make docker-down  - Stop API container"
	@echo "  make docker-logs  - Tail API container logs"
	@echo "  make test         - Run backend test suite"
	@echo "  make test-backend - Run all backend unittest tests"
	@echo "  make test-routes  - Run lightweight route tests"
	@echo "  make test-syntax  - Python syntax check for backend app modules/tests"

sync:
	$(UV) sync

sync-dev:
	$(UV) sync --extra test --extra dev

lock:
	$(UV) lock

run:
	$(UV) run uvicorn app:app --host 0.0.0.0 --port 8000 --reload

migrate-users:
	$(UV) run python helpers/migrate_user_profiles_to_sqlite.py --delete-json

docker-build:
	docker compose build

docker-up:
	docker compose up --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f app

test: test-backend

test-backend:
	$(UV) run python -m unittest discover -s tests -p "test_*.py" -v

test-routes:
	$(UV) run python -m unittest tests.test_app_routes -v

test-syntax:
	$(UV) run python -m py_compile \
		app.py \
		app_shared.py \
		api_helpers.py \
		api_schemas.py \
		routes_auth.py \
		routes_catalog.py \
		routes_users.py \
		user_services.py \
		tests/test_app_routes.py \
		tests/test_sqlite_profile_integration.py
