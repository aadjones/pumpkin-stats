# ---------------------------------------------------------------------
# Run `make help` to see available commands
# ---------------------------------------------------------------------
.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	| awk -F':.*?## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}' \
	| sort

# ---------- config ----------
VENV_DIR := env
PY        := $(VENV_DIR)/bin/python
PIP       := $(VENV_DIR)/bin/pip
STREAMLIT := $(VENV_DIR)/bin/streamlit

# ---------- helpers ----------
$(VENV_DIR)/bin/activate: requirements.txt requirements-dev.txt ## (internal) build venv & install deps
	@echo "🔧  Creating virtual-env & installing deps …"
	@python -m venv $(VENV_DIR)
	@$(PIP) install -r requirements.txt -r requirements-dev.txt
	@touch $(VENV_DIR)/bin/activate

# ---------- one-shot bootstrap ----------
setup: $(VENV_DIR)/bin/activate ## Create env/, git init, pre-commit install
	@if [ ! -d .git ]; then \
		echo "🔧  Initialising Git repo"; \
		git init -q && git switch -c main; \
	fi
	@$(VENV_DIR)/bin/pre-commit install
	@echo "✅  Env ready"

# ---------- repeatable tasks ----------
install: $(VENV_DIR)/bin/activate ## Idempotent dependency install

dev: install ## Run Streamlit app locally
	$(STREAMLIT) run app.py

fmt: install ## Auto-format with isort & black (skips env/ and .git/)
	@echo "✨  Formatting with black + isort"
	@$(VENV_DIR)/bin/isort --skip=$(VENV_DIR) --skip=.git .
	@$(VENV_DIR)/bin/black --exclude '^(env|\.git)/' .

test: install               ## Run pytest suite
	PYTHONPATH=. $(VENV_DIR)/bin/pytest -q

deploy: ## Commit & push to Streamlit Cloud
	git add -A && git commit -m "deploy" || true
	git push origin main
	@echo "🚀  Deploy pushed — check your hosting dashboard."

clean: ## Delete the virtual-env
	rm -rf $(VENV_DIR)
