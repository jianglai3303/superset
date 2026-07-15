# Local Development Setup

## Prerequisites

- Python 3.11 (`/usr/local/bin/python3.11`)
- Node.js 18+
- Docker (for Postgres, Redis, Keycloak)

## 1. Start Supporting Services

```bash
docker compose up -d db redis keycloak
```

## 2. Python Backend

Create venv (first time only):

```bash
python3.11 -m venv venv
pip install "setuptools<71"
pip install llvmlite==0.42.0 --only-binary :all:
grep -v "numba\|llvmlite" requirements/base.txt > /tmp/reqs.txt
pip install -r /tmp/reqs.txt numba==0.59.1 psycopg2-binary --only-binary llvmlite
pip install -e . --no-deps
```

Start the backend:

```bash
PYTHONPATH=docker/pythonpath_dev \
DATABASE_DIALECT=postgresql \
DATABASE_USER=superset \
DATABASE_PASSWORD=superset \
DATABASE_HOST=localhost \
DATABASE_PORT=5432 \
DATABASE_DB=superset \
EXAMPLES_USER=examples \
EXAMPLES_PASSWORD=examples \
EXAMPLES_HOST=localhost \
EXAMPLES_PORT=5432 \
EXAMPLES_DB=examples \
REDIS_HOST=localhost \
REDIS_PORT=6379 \
REDIS_CELERY_DB=0 \
REDIS_RESULTS_DB=1 \
FLASK_APP=superset \
SUPERSET_SECRET_KEY="devkey123devkey123devkey123devkey123devkey123" \
venv/bin/superset run -p 8088 --with-threads --reload --debugger
```

Backend runs at: http://localhost:8088

## 3. Frontend

```bash
cd superset-frontend
npm install webpack webpack-cli --no-save --ignore-scripts
node_modules/.bin/webpack --mode=development --color --watch
```

## Notes

- Keycloak runs at http://localhost:8080 (admin/admin)
- The `Superset` OAuth client in Keycloak must exist with redirect URI `http://localhost:8088/*` and secret `Hsq03ihgnbuw26oThwlBP6qzHa7teuTT`
- `SUPERSET_SECRET_KEY` is regenerated each run — sessions won't persist across restarts. Hardcode a fixed value to avoid re-login.
