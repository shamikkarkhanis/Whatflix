PYTHON ?= python3

.PHONY: help test test-backend test-routes test-syntax

help:
	@echo "Available targets:"
	@echo "  make test         - Run backend test suite"
	@echo "  make test-backend - Run all backend unittest tests"
	@echo "  make test-routes  - Run lightweight route tests"
	@echo "  make test-syntax  - Python syntax check for backend app modules/tests"

test: test-backend

test-backend:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

test-routes:
	$(PYTHON) -m unittest tests.test_app_routes -v

test-syntax:
	$(PYTHON) -m py_compile \
		app.py \
		app_shared.py \
		api_helpers.py \
		api_schemas.py \
		routes_auth.py \
		routes_catalog.py \
		routes_users.py \
		user_services.py \
		tests/test_app_routes.py
