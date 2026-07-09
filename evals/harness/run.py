"""NL evaluation harness for LAIA assistant.

Usage:
  PYTHONPATH=src python -m evals.harness.run \\
    --utterances evals/utterances/phase3_create_search.json \\
    --pipeline two_call \\
    --model qwen2.5:7b

Without a live Ollama, use --dry-run to validate utterance loading only.
With --mock, runs against FakeOllama heuristics for CI smoke (not accuracy).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from laia.config import get_settings
from laia.db import Base
from laia.orchestrator.pipeline import Orchestrator
from laia.schemas.events import EventCreate
from laia.services.calendar import CalendarService
from laia.services.conversation import ConversationStore
from laia.services.ollama import OllamaClient

ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = ROOT / "evals" / "results"


async def _reset_db(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            __import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        )
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def _seed(session: AsyncSession, seed: str | None) -> dict[str, Any]:
    """Seed calendar fixtures for an utterance. Returns context for follow-ups."""
    cal = CalendarService(session)
    tz = ZoneInfo(get_settings().laia_timezone)
    ctx: dict[str, Any] = {}
    if seed in {None, "none"}:
        return ctx

    if seed == "standard":
        events = [
            ("Dentist", datetime(2026, 7, 14, 14, 0, tzinfo=tz), 60),
            ("Gym", datetime(2026, 7, 10, 18, 0, tzinfo=tz), 60),
            ("Standup", datetime(2026, 7, 11, 9, 0, tzinfo=tz), 30),
            ("Lunch with Sam", datetime(2026, 7, 12, 12, 0, tzinfo=tz), 60),
            ("Haircut", datetime(2026, 9, 1, 16, 30, tzinfo=tz), 45),
            ("Board meeting", datetime(2026, 7, 22, 13, 0, tzinfo=tz), 120),
            ("Flight to NYC", datetime(2026, 10, 12, 6, 15, tzinfo=tz), 180),
            ("Interview with Acme", datetime(2026, 11, 5, 15, 0, tzinfo=tz), 60),
            ("Coffee with Jordan", datetime(2026, 12, 1, 8, 30, tzinfo=tz), 30),
            ("Walking meeting", datetime(2026, 7, 17, 14, 0, tzinfo=tz), 30),
        ]
        for title, start, mins in events:
            await cal.create_event(
                EventCreate(
                    title=title,
                    start_at=start,
                    end_at=start + timedelta(minutes=mins),
                    timezone=str(tz),
                )
            )
    elif seed == "two_dentists":
        for start in (
            datetime(2026, 7, 14, 14, 0, tzinfo=tz),
            datetime(2026, 8, 3, 10, 0, tzinfo=tz),
        ):
            await cal.create_event(
                EventCreate(
                    title="Dentist",
                    start_at=start,
                    end_at=start + timedelta(hours=1),
                    timezone=str(tz),
                )
            )
    elif seed == "pending_delete":
        event = await cal.create_event(
            EventCreate(
                title="Dentist",
                start_at=datetime(2026, 7, 14, 14, 0, tzinfo=tz),
                end_at=datetime(2026, 7, 14, 15, 0, tzinfo=tz),
                timezone=str(tz),
            )
        )
        ctx["event_id"] = str(event.id)
    await session.commit()
    return ctx


def _passed(utterance: dict[str, Any], response: Any, *, silent_wrong_write: bool) -> tuple[bool, str | None]:
    if silent_wrong_write:
        return False, "silent_wrong_write"

    expected = utterance["expected_command"]
    actual_command = None
    if response.action:
        actual_command = response.action.command
    elif response.pending and response.pending.command:
        actual_command = response.pending.command
    elif expected in {"none", "unclear", "multi_intent"}:
        # Soft rejects have no action/pending command; treat reply-only as matching class
        # if no write occurred. Harness records expected; pass if no action.
        if response.action is None:
            return True, None
    else:
        actual_command = None

    if utterance.get("expect_pending_type"):
        if response.pending is None or response.pending.type != utterance["expect_pending_type"]:
            return False, f"expected pending {utterance['expect_pending_type']}"
        return True, None

    if utterance.get("expect_action") is False:
        if response.action is not None:
            return False, "unexpected action"
        return True, None

    if utterance.get("follow_up") and utterance.get("expect_confirm") is True:
        if response.action and response.action.command == "delete_event":
            return True, None
        return False, "expected delete after yes"

    if utterance.get("follow_up") and utterance.get("expect_confirm") is False:
        if response.action is None:
            return True, None
        return False, "delete should not execute on no"

    if expected in {"none", "unclear", "multi_intent"}:
        if response.action is None:
            return True, None
        return False, f"expected no action for {expected}"

    if actual_command != expected and not (
        response.pending and response.pending.command == expected
    ):
        # For create/search happy paths we need the action command.
        if utterance.get("expect_action") and (not response.action or response.action.command != expected):
            return False, f"expected {expected}, got {actual_command}"
        if not utterance.get("expect_action") and actual_command != expected:
            return False, f"expected {expected}, got {actual_command}"

    if utterance.get("expect_action") and response.action is None and response.pending is None:
        return False, "expected action"

    return True, None


async def run_eval(
    *,
    utterances_path: Path,
    model: str,
    pipeline: str,
    database_url: str,
    dry_run: bool = False,
    limit: int | None = None,
) -> Path:
    utterances = json.loads(utterances_path.read_text())
    if limit:
        utterances = utterances[:limit]

    run_id = (
        f"{datetime.now(tz=UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}"
        f"-{model.replace(':', '')}-{pipeline}"
    )
    out_path = RESULTS_DIR / f"{run_id}.jsonl"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print(f"Dry run: {len(utterances)} utterances from {utterances_path}")
        return out_path

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    ollama = OllamaClient(base_url=settings.ollama_base_url, model=model)

    passed = 0
    silent_wrong = 0

    with out_path.open("w", encoding="utf-8") as fh:
        for utterance in utterances:
            await _reset_db(engine)
            store = ConversationStore(ttl_minutes=30)
            async with factory() as session:
                ctx = await _seed(session, utterance.get("seed"))
                orch = Orchestrator(session, ollama=ollama, store=store, pipeline=pipeline)

                started = time.perf_counter()
                notes = None
                actual_command = None
                try:
                    if utterance.get("follow_up") and utterance.get("seed") == "pending_delete":
                        # Prime confirmation pending state.
                        store.set_pending(
                            store.get_or_create().conversation_id,
                            pending_type="confirmation",
                            command="delete_event",
                            target_event_id=ctx["event_id"],
                        )
                        cid = next(iter(store._states))
                        response = await orch.handle(
                            message=utterance["message"],
                            conversation_id=cid,
                        )
                    else:
                        response = await orch.handle(message=utterance["message"])

                    if response.action:
                        actual_command = response.action.command
                    elif response.pending:
                        actual_command = response.pending.command

                    # Detect silent wrong writes: action command differs from expected write command.
                    wrong_write = False
                    if response.action and utterance["expected_command"] in {
                        "create_event",
                        "update_event",
                        "delete_event",
                    }:
                        if response.action.command != utterance["expected_command"]:
                            wrong_write = True
                            silent_wrong += 1

                    ok, notes = _passed(utterance, response, silent_wrong_write=wrong_write)
                except Exception as exc:  # noqa: BLE001
                    ok = False
                    notes = f"exception: {exc}"
                    response = None

                latency_ms = int((time.perf_counter() - started) * 1000)
                if ok:
                    passed += 1

                record = {
                    "run_id": run_id,
                    "model": model,
                    "pipeline": pipeline,
                    "utterance_id": utterance["id"],
                    "passed": ok,
                    "expected_command": utterance["expected_command"],
                    "actual_command": actual_command,
                    "latency_ms": latency_ms,
                    "notes": notes,
                    "reply": getattr(response, "reply", None),
                }
                fh.write(json.dumps(record) + "\n")
                print(
                    f"{'PASS' if ok else 'FAIL'} {utterance['id']} "
                    f"expected={utterance['expected_command']} actual={actual_command} "
                    f"{latency_ms}ms"
                )
                await session.commit()

    await ollama.aclose()
    await engine.dispose()

    total = len(utterances)
    rate = (passed / total * 100) if total else 0
    summary = {
        "run_id": run_id,
        "model": model,
        "pipeline": pipeline,
        "total": total,
        "passed": passed,
        "success_rate": rate,
        "silent_wrong_writes": silent_wrong,
        "results_path": str(out_path),
    }
    summary_path = RESULTS_DIR / f"{run_id}.summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="LAIA NL eval harness")
    parser.add_argument(
        "--utterances",
        type=Path,
        default=ROOT / "evals/utterances/phase3_create_search.json",
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--pipeline", default="two_call", choices=["two_call", "single_call"])
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    settings = get_settings()
    model = args.model or settings.ollama_model
    database_url = args.database_url or settings.database_url

    asyncio.run(
        run_eval(
            utterances_path=args.utterances,
            model=model,
            pipeline=args.pipeline,
            database_url=database_url,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    )


if __name__ == "__main__":
    main()
