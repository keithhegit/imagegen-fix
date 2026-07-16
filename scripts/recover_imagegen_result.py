#!/usr/bin/env python3
"""Recover a Base64 image result from Codex image-generation session records."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass
class Candidate:
    timestamp: datetime
    timestamp_text: str
    log_path: Path
    line_number: int
    raw_line: str
    payload: dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recover and validate an imagegen Base64 result from Codex session JSONL."
    )
    parser.add_argument("--out", required=True, help="Destination image path.")
    parser.add_argument("--raw-json", help="Optional path for the exact selected JSONL record.")
    parser.add_argument("--log", action="append", help="Session JSONL file; repeat as needed.")
    parser.add_argument(
        "--sessions-root",
        help="Sessions root. Defaults to $CODEX_HOME/sessions or ~/.codex/sessions.",
    )
    parser.add_argument("--image-id", help="Select an exact image_generation_call id.")
    parser.add_argument(
        "--prompt-contains",
        help="Select records whose revised_prompt contains this text, case-insensitively.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=50,
        help="Maximum recent session files to scan when --log is omitted (default: 50).",
    )
    return parser.parse_args()


def default_sessions_root() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    return Path(codex_home).expanduser() / "sessions" if codex_home else Path.home() / ".codex" / "sessions"


def session_logs(args: argparse.Namespace) -> list[Path]:
    if args.log:
        logs = [Path(value).expanduser().resolve() for value in args.log]
    else:
        root = Path(args.sessions_root).expanduser() if args.sessions_root else default_sessions_root()
        if not root.is_dir():
            raise FileNotFoundError(f"Sessions root does not exist: {root}")
        logs = sorted(
            root.rglob("*.jsonl"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[: args.max_files]
    missing = [str(path) for path in logs if not path.is_file()]
    if missing:
        raise FileNotFoundError("Session log not found: " + ", ".join(missing))
    if not logs:
        raise FileNotFoundError("No session JSONL files found")
    return logs


def parse_timestamp(value: object, log_path: Path) -> tuple[datetime, str]:
    text = value if isinstance(value, str) else ""
    if text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed, text
        except ValueError:
            pass
    fallback = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc)
    return fallback, fallback.isoformat()


def iter_candidates(logs: Iterable[Path], args: argparse.Namespace) -> Iterable[Candidate]:
    prompt_filter = args.prompt_contains.casefold() if args.prompt_contains else None
    for log_path in logs:
        with log_path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if '"image_generation_call"' not in raw_line or '"result"' not in raw_line:
                    continue
                try:
                    record = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                payload = record.get("payload")
                if not isinstance(payload, dict) or payload.get("type") != "image_generation_call":
                    continue
                result = payload.get("result")
                if not isinstance(result, str) or not result.strip():
                    continue
                if args.image_id and payload.get("id") != args.image_id:
                    continue
                revised_prompt = payload.get("revised_prompt")
                if prompt_filter and prompt_filter not in str(revised_prompt or "").casefold():
                    continue
                timestamp, timestamp_text = parse_timestamp(record.get("timestamp"), log_path)
                yield Candidate(
                    timestamp=timestamp,
                    timestamp_text=timestamp_text,
                    log_path=log_path,
                    line_number=line_number,
                    raw_line=raw_line.rstrip("\r\n"),
                    payload=payload,
                )


def detect_image(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif", "image/gif"
    raise ValueError("Decoded result does not have a recognized image signature")


def decode_result(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Invalid Base64 image result: {exc}") from exc


def normalized_output_path(value: str, extension: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.suffix:
        path = path.with_suffix(f".{extension}")
    elif path.suffix.lower().lstrip(".") not in {extension, "jpeg" if extension == "jpg" else extension}:
        raise ValueError(
            f"Output suffix {path.suffix!r} does not match decoded {extension.upper()} data"
        )
    return path


def main() -> int:
    args = parse_args()
    try:
        logs = session_logs(args)
        candidates = list(iter_candidates(logs, args))
        if not candidates:
            raise LookupError("No matching image_generation_call with a non-empty result was found")
        candidate = max(candidates, key=lambda item: (item.timestamp, str(item.log_path), item.line_number))
        result_text = candidate.payload["result"].strip()
        image_bytes = decode_result(result_text)
        extension, media_type = detect_image(image_bytes)
        output_path = normalized_output_path(args.out, extension)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)

        raw_path = None
        if args.raw_json:
            raw_path = Path(args.raw_json).expanduser().resolve()
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(candidate.raw_line + "\n", encoding="utf-8")

        summary = {
            "success": True,
            "image_id": candidate.payload.get("id"),
            "status": candidate.payload.get("status"),
            "timestamp": candidate.timestamp_text,
            "source_log": str(candidate.log_path),
            "source_line": candidate.line_number,
            "revised_prompt": candidate.payload.get("revised_prompt"),
            "base64_length": len(result_text),
            "decoded_bytes": len(image_bytes),
            "format": extension,
            "media_type": media_type,
            "sha256": hashlib.sha256(image_bytes).hexdigest(),
            "output": str(output_path),
            "raw_json": str(raw_path) if raw_path else None,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (FileNotFoundError, LookupError, OSError, ValueError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
