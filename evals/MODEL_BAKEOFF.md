# Model & pipeline bakeoff

Phase 3 requires comparing 2–3 local models and optionally a single-call pipeline against the default two-call pipeline.

## Prerequisites (Linux GPU target)

```bash
docker compose up -d
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull llama3.1:8b
# optional quality jump if VRAM allows:
# docker compose exec ollama ollama pull qwen2.5:14b
```

## Run create/search eval (≥50 utterances)

```bash
export DATABASE_URL=postgresql+asyncpg://laia:laia@localhost:5432/laia_test
export OLLAMA_BASE_URL=http://127.0.0.1:11434   # only if you temporarily publish Ollama for host-side eval
# Preferred: run harness inside the api container so it uses http://ollama:11434

PYTHONPATH=src python -m evals.harness.run \
  --utterances evals/utterances/phase3_create_search.json \
  --pipeline two_call \
  --model qwen2.5:7b
```

Repeat with `--model llama3.1:8b` (and optionally `qwen2.5:14b`).

## Single-call benchmark

The discriminated-union schema lives in `src/laia/schemas/single_call.py`.
Use `--pipeline single_call` once the single-call orchestrator path is wired for bakeoff runs.
Default production path remains **two_call** until evidence shows single-call matches accuracy with better latency.

## Decision record

After runs, update this table and set `OLLAMA_MODEL` in `.env`:

| Model | Pipeline | Create/search success | p95 latency | Notes |
|-------|----------|----------------------|-------------|-------|
| qwen2.5:7b | two_call | _TBD on GPU host_ | _TBD_ | Default candidate |
| llama3.1:8b | two_call | _TBD_ | _TBD_ | |
| qwen2.5:14b | two_call | _TBD_ | _TBD_ | Optional |

**Chosen default:** `qwen2.5:7b` + `two_call` until bakeoff results replace this.

Exit criteria from the project plan:

- ≥85% success on create/search eval
- Relative-date cases acceptable
- Results persisted under `evals/results/*.jsonl`
