"""Command line interface: validate and extract (recorded replies only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .core import (
    MAX_JSON_CHARS,
    ValidationIssue,
    invoice_from_obj,
    invoice_to_dict,
    load_json,
    validate_invoice,
)
from .errors import InvoiceError
from .extract import extract_invoice
from .llm import RecordedLLM, RecordingExhaustedError

_MAX_TEXT_CHARS = 100_000


def _read(path: str, limit: int) -> str:
    try:
        with Path(path).open(encoding="utf-8") as fh:
            data = fh.read(limit + 1)
    except (OSError, UnicodeDecodeError):
        raise InvoiceError("extraction_failed", "cannot read input file") from None
    if len(data) > limit:
        raise InvoiceError("input_too_large", "input file exceeds the limit")
    return data


def _issue(i: ValidationIssue) -> dict[str, str]:
    return {"code": i.code, "path": i.path, "message": i.message, "severity": i.severity}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="invoice-extractor")
    sub = parser.add_subparsers(dest="command", required=True)
    val = sub.add_parser("validate", help="validate an invoice JSON file")
    val.add_argument("invoice")
    ext = sub.add_parser("extract", help="extract from text using recorded replies")
    ext.add_argument("file")
    ext.add_argument("--recorded", required=True)
    return parser


def _run(args: argparse.Namespace) -> int:
    out: dict[str, Any]
    if args.command == "validate":
        invoice = invoice_from_obj(load_json(_read(args.invoice, MAX_JSON_CHARS)))
        issues = validate_invoice(invoice)
        out = {"issues": [_issue(i) for i in issues]}
    else:
        text = _read(args.file, _MAX_TEXT_CHARS)
        replies = load_json(_read(args.recorded, MAX_JSON_CHARS))
        if not isinstance(replies, list) or not all(isinstance(r, str) for r in replies):
            raise InvoiceError("extraction_failed", "recorded replies must be a list of strings")
        result = extract_invoice(text, RecordedLLM(replies))
        issues = list(result.issues)
        out = {
            "invoice": invoice_to_dict(result.invoice),
            "issues": [_issue(i) for i in issues],
            "attempts": result.attempts,
        }
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 1 if any(i.severity == "error" for i in issues) else 0


def main(argv: list[str] | None = None) -> int:
    """Run the CLI; 0 ok, 1 error issues, 2 usage, IO or parse error."""
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        return _run(args)
    except (InvoiceError, RecordingExhaustedError) as exc:
        code = getattr(exc, "code", "recording_exhausted")
        sys.stderr.write(f"error: {code}\n")
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
