#!/usr/bin/env python3
"""Thin CLI wrapper for LAIA assistant chat."""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat with the LAIA assistant")
    parser.add_argument("message", nargs="?", help="Message to send (or use --interactive)")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("LAIA_BASE_URL", "http://127.0.0.1:8000"),
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("LAIA_API_KEY", "dev-api-key-change-me"),
    )
    parser.add_argument("--conversation-id", default=None)
    parser.add_argument("-i", "--interactive", action="store_true")
    args = parser.parse_args()

    headers = {"X-API-Key": args.api_key, "Content-Type": "application/json"}
    conversation_id = args.conversation_id

    def send(message: str) -> dict:
        nonlocal conversation_id
        payload = {"message": message, "conversation_id": conversation_id}
        with httpx.Client(base_url=args.base_url, timeout=120.0) as client:
            response = client.post("/api/assistant/chat", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        conversation_id = data.get("conversation_id")
        return data

    if args.interactive or not args.message:
        print("LAIA assistant (Ctrl-D to exit)")
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                print()
                return 0
            if not line:
                continue
            data = send(line)
            print(data["reply"])
            if data.get("pending"):
                print(f"[pending] {json.dumps(data['pending'])}")
            if data.get("action"):
                print(f"[action] {json.dumps(data['action'])}")
        return 0

    data = send(args.message)
    print(data["reply"])
    if data.get("action"):
        print(json.dumps(data["action"], indent=2))
    if data.get("pending"):
        print(json.dumps(data["pending"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
