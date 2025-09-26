# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

**Setup (one-time bootstrap):**
```bash
# macOS/Linux
make setup  # Creates env/, installs deps, git init, pre-commit install

# Windows
.\run.ps1 setup  # Creates env/, installs deps, git init, pre-commit install
```

**Development workflow:**
```bash
# macOS/Linux
make dev    # Run Streamlit app locally (streamlit run app.py)
make fmt    # Auto-format with isort & black
make test   # Run pytest suite

# Windows
.\run.ps1 dev    # Run Streamlit app locally (streamlit run app.py)
.\run.ps1 fmt    # Auto-format with isort & black
.\run.ps1 test   # Run pytest suite
```

**Single test:**
```bash
# macOS/Linux
PYTHONPATH=. env/bin/pytest tests/test_charts.py::test_line_chart -v

# Windows (PowerShell)
$env:PYTHONPATH="."; .\env\Scripts\activate.ps1; pytest tests/test_charts.py::test_line_chart -v
```

## Architecture Overview

This is a **Streamlit finance dashboard** built from a cookiecutter template with a modular structure:

- **`app.py`** - Main Streamlit entry point, loads data from `data/demo.csv`, renders UI with sidebar metric selection
- **`modules/`** - Core functionality:
  - `charts.py` - Plotly chart creation (line charts with auto-color lookup)
  - `palette.py` - Primary color theme (`#DB6D72`)
  - `constants.py` - Centralized labels and color mappings for different metrics
- **`data/demo.csv`** - Sample dataset (replaceable with real data)
- **`scripts/gen_demo_data.py`** - Utility to generate mock data

**Key patterns:**
- Uses `@st.cache_data(ttl=0)` for data loading
- Color/label lookup system via `constants.py` for consistent theming
- Modular chart creation with auto-styling based on column names

## Code Style

- **Black** formatting (120 char line length)
- **isort** import sorting
- Pre-commit hooks enforce formatting
- Virtual env in `env/` directory (excluded from formatters)

## Data Flow

1. `app.py` loads CSV via cached `load_data()` function
2. User selects metric from sidebar dropdown (all columns except first)
3. `charts.line_chart()` creates Plotly figure with auto-color from `constants.COLORS`
4. Chart rendered with `st.plotly_chart(use_container_width=True)`