# RouteDesk backend (MVP)

FastAPI service for ticket intake, transparent demo classification, routing, workflow events, feedback and operational metrics. It persists to SQLite by default and can use PostgreSQL by setting `DATABASE_URL`.

> The included classifier is a small rule-based demo, not a trained or validated AI model. Confidence values are illustrative heuristics; do not enable unattended production routing based on them. Use a human-reviewed dataset, held-out evaluation, access controls and privacy review before a real pilot.

## Run locally

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for the interactive API. SQLite data is stored in `backend/routedesk.db` when started from this directory.

## Endpoints

- `GET /api/health` — health check
- `POST /api/classify` — classify text without creating a ticket
- `POST /api/tickets` — create a ticket and record `created`/`classified` events
- `GET /api/tickets` — list with optional `status`, `department`, `limit`, `offset`
- `GET /api/tickets/{id}` — retrieve ticket
- `PATCH /api/tickets/{id}` — update status, assign executor, or add comment
- `GET /api/tickets/{id}/events` — audit trail
- `POST /api/tickets/{id}/reroute` — change department and record actor/reason/from-to
- `POST /api/tickets/{id}/feedback` — save requester rating
- `GET /api/metrics` — ticket counts, reroutes, confidence and department volumes

### Create ticket example

```bash
curl -X POST http://localhost:8000/api/tickets \\
  -H 'Content-Type: application/json' \\
  -d '{"description":"В аудитории 305 не работает проектор, завтра лекция","requester":"Иван Иванов"}'
```

## Connect the HTML prototype

Serve the HTML and API locally. The API allows CORS origins `*` for the demo by default; set `CORS_ORIGINS` to a comma-separated allowlist outside local development. The current prototype still has its own demo interactions and does not yet call these endpoints.

## Production gaps (not implemented)

Authentication/RBAC, PostgreSQL migrations, file upload storage/scanning, notification delivery, rate limits, audit retention, backups, model evaluation and production deployment need to be added before handling real employee data. Do not send sensitive request text to external AI services without an approved privacy/security design.
