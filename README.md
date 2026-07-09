# LAIA

LAIA (Local AI Assistant) is a self-hosted assistant that runs on a desktop machine, uses local open-source models via Ollama, and exposes a secure localhost API for calendar management through REST and natural language.

## MVP features

- Docker Compose stack: `api`, `postgres`, `ollama`
- Calendar REST CRUD (`/api/events`)
- Natural-language assistant (`POST /api/assistant/chat`)
- Structured LLM outputs validated with Pydantic
- Deterministic relative-date resolution in Python
- Clarification, disambiguation, and delete confirmation flows
- NL evaluation harness with persisted JSONL results

## Quick start (Linux GPU target)

Requirements: Docker, Docker Compose, NVIDIA driver, `nvidia-container-toolkit`.

```bash
cp .env.example .env
# edit LAIA_API_KEY and LAIA_TIMEZONE

docker compose up --build -d

# Pull a model into the internal Ollama service (no host port published)
docker compose exec ollama ollama pull qwen2.5:7b

# Health
curl -s http://127.0.0.1:8000/healthz
curl -s -H "X-API-Key: $LAIA_API_KEY" http://127.0.0.1:8000/api/health/ollama
```

API binds to `127.0.0.1:8000` only. Ollama is reachable by the API on the Docker network and is **not** published on the host.

### Enable GPU for Ollama

Uncomment the `deploy.resources.reservations.devices` block under `ollama` in `docker-compose.yml` (NVIDIA).

## macOS / API-only development

Docker Desktop on Mac will not use the NVIDIA GPU target.

Recommended workflow:

1. Run API + Postgres via Compose (you can stop the `ollama` service).
2. Install Ollama natively on Mac, or point at a remote Linux GPU host.
3. Set in `.env`:

```bash
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b
```

Treat Linux GPU eval results as the source of truth for latency and accuracy.

## Authentication

All `/api/*` endpoints (except `/healthz`) require:

```http
X-API-Key: <LAIA_API_KEY>
```

## REST calendar API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/events` | Create event |
| GET | `/api/events?q=&start=&end=` | Search events |
| GET | `/api/events/{id}` | Get event |
| PATCH | `/api/events/{id}` | Update event |
| DELETE | `/api/events/{id}` | Delete event |

Example:

```bash
curl -s -X POST http://127.0.0.1:8000/api/events \
  -H "X-API-Key: $LAIA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Dentist appointment",
    "start_at": "2026-07-14T14:00:00-05:00",
    "end_at": "2026-07-14T15:00:00-05:00",
    "timezone": "America/Chicago",
    "all_day": false
  }'
```

## Assistant chat

```bash
curl -s -X POST http://127.0.0.1:8000/api/assistant/chat \
  -H "X-API-Key: $LAIA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a dentist appointment next Tuesday at 2pm"}'
```

Conversation state supports clarification, disambiguation, and delete confirmation via `conversation_id`.

### Optional CLI

```bash
PYTHONPATH=src python scripts/laia_chat.py -i
# or
PYTHONPATH=src python scripts/laia_chat.py "What do I have tomorrow?"
```

## Postman

Import [`postman/LAIA.postman_collection.json`](postman/LAIA.postman_collection.json).

## Tests

```bash
# Requires local Postgres with databases laia / laia_test (or Compose postgres published)
export DATABASE_URL=postgresql+asyncpg://laia:laia@localhost:5432/laia_test
export LAIA_API_KEY=test-api-key
PYTHONPATH=src pytest tests/ -v
```

## Evaluation

Utterance sets:

- `evals/utterances/phase3_create_search.json` (≥50 create/search)
- `evals/utterances/full_suite.json` (≥100 across all commands)

```bash
PYTHONPATH=src python -m evals.harness.run --dry-run
PYTHONPATH=src python -m evals.harness.run \
  --utterances evals/utterances/full_suite.json \
  --model qwen2.5:7b
```

See [`evals/MODEL_BAKEOFF.md`](evals/MODEL_BAKEOFF.md) for model comparison steps.

Results are written to `evals/results/*.jsonl`.

## Environment variables

| Variable | Description |
|----------|-------------|
| `LAIA_API_KEY` | Single MVP API key |
| `DATABASE_URL` | Postgres URL (`postgresql+asyncpg://...`) |
| `OLLAMA_BASE_URL` | Usually `http://ollama:11434` in Compose |
| `OLLAMA_MODEL` | Selected model after bakeoff |
| `LAIA_TIMEZONE` | Default IANA timezone |
| `CONVERSATION_TTL_MINUTES` | Pending state TTL (default 15) |
| `LOG_LEVEL` | Default `INFO` |

## Project layout

```text
src/laia/          FastAPI app, services, orchestrator
alembic/           Migrations
tests/             Unit + integration tests
evals/             Utterances + harness
postman/           Manual API collection
docker-compose.yml api + postgres + ollama
Dockerfile.api     Runtime API image
Dockerfile         Dev/agent image (unchanged)
```

## MVP acceptance checklist

1. `docker compose up` starts API, Postgres, and Ollama on the Linux GPU target
2. Ollama reachable by API, not exposed on a host port
3. All five REST operations covered by integration tests
4. `/api/assistant/chat` supports create/search/get/update/delete
5. Clarification + confirmation via `conversation_id`
6. Deletes require confirmation
7. Updates use resolved event context before patch extraction
8. Relative dates resolved in Python (`laia.services.dates`)
9. ≥100 NL eval utterances by Phase 4 set
10. Eval results persisted as JSONL
11. Full-command eval ≥80% on GPU host (run harness to measure)
12. Create/search eval ≥85% on GPU host
13. Zero silent wrong writes in eval runs
14. Simple NL p95 ≤8s on target hardware
15. README + Postman sufficient for a fresh local run

## Out of scope (MVP)

Mobile client, tunnels/P2P, external calendar sync, recurring events, multi-user auth, STT/TTS, filesystem tools, job queues, multi-intent execution.
