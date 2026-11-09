# RouteDesk backend and connected web demo

RouteDesk currently has a standalone prototype and an API-connected workflow demo.

## Start the complete demo

Requires Docker Compose:

```bash
docker compose up --build
```

Open `http://localhost:8080`. FastAPI docs are at `http://localhost:8000/docs`; health check is `http://localhost:8000/api/health`. The HTML UI loads tickets, history and metrics from the API and supports create → classify/route → assign → reroute → resolve → metrics refresh.

## Run without Docker

Start the API from the repository root:

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then serve `frontend/index.html` using any static web server (for example `python -m http.server 8080` from `frontend/`) and open `http://localhost:8080`.

The frontend defaults to `http://localhost:8000` for the API. Override it with `?api=http://your-api-host:8000` if needed. CORS origins are configured through the backend `CORS_ORIGINS` environment variable.

The original UI prototype remains available in `routedesk_prototype (1).html`. See [backend/README.md](backend/README.md) for API details and production limitations.
