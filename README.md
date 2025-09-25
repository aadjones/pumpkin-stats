# Finance Dashboard

[![Deploy to Streamlit](https://img.shields.io/badge/Deploy-Streamlit%20Cloud-%23FF4B4B)](https://streamlit.io/)

Dashboard for tracking cash flow

---

## 🚀 Quick start

Generate the project with Cookiecutter

```bash
cookiecutter gh:aadjones/streamlit-mini-template

cd finance_dashboard
```

One-command bootstrap (creates env/, installs deps, git init, pre-commit)

```bash
make setup
```

Run the dashboard locally

```bash
make dev
```

(Optional) Auto-format & lint

```bash
make fmt
```

Run test suite

```bash
make test
```

(Optional) Create a GitHub repo and run

```bash
git remote add origin git@github.com:<user>/<repo>.git
git push -u origin main
```

---

## 📊 Demo data

The repo ships with a tiny sample CSV at **`data/demo.csv`** so the dashboard shows charts on first run.  
Replace it with your own file — or generate new mock data:

    python scripts/gen_demo_data.py --rows 365

---

## ☁️ Deploy

**Streamlit Cloud**

- Link the repo at <https://streamlit.io/cloud>
- Push to **main** → Cloud auto-builds (or run `make deploy`)

Happy hacking! 🌱
