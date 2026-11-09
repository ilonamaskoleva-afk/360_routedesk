# RouteDesk

RouteDesk is an internal-request routing and process-visibility prototype. The repository currently includes a standalone HTML demo and a FastAPI MVP backend.

## Backend

See [backend/README.md](backend/README.md) for setup, API endpoints, sample requests, and production limitations.

Quick start with Docker:

```bash
docker compose up --build
```

API documentation: `http://localhost:8000/docs`.

The routing classifier is rule-based demo logic, not a validated ML model. Metrics shown by the HTML prototype are sample/demo values; they should not be presented as measured pilot outcomes.
