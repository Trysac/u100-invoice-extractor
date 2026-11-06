"""Amount parsing, data model, validation and strict JSON loading."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Literal

from .errors import AmbiguousAmountError, InvoiceError

MAX_AMOUNT_CHARS = 64
MAX_JSON_CHARS = 200_000
MAX_LINES = 1000
MAX_FIELD_CHARS = 500

# SIX ISO 4217 List One, checked 2026-11-05.
_EXPONENT_GROUPS = (
    (0, "JPY KRW CLP ISK PYG VND UGX XAF XOF"),
    (3, "BHD IQD JOD KWD LYD OMR TND"),
    (4, "CLF UYW"),
    (2, "USD EUR GBP CHF CAD AUD CNY HKD SGD SEK NOK DKK PLN CZK MXN BRL INR ZAR"),
)
ISO_4217_EXPONENTS: Mapping[str, int] = MappingProxyType(
    {code: exp for exp, codes in _EXPONENT_GROUPS for code in codes.split()}
)

Kind = Literal["item", "discount", "shipping", "fee"]
_KINDS = ("item", "discount", "shipping", "fee")

_SYMBOLS = "$\u20ac\u00a3\u00a5\u20b9\u20a9\u20bd"
_GROUP_CHARS = " \u00a0\u202f\u2009'\u2019"
_DIGITS = "0123456789"
_ISO_START = re.compile(r"[A-Z]{3}")
_ISO_END = re.compile(r"[A-Z]{3}\Z")
_FENCE = re.compile(r"\A\s*```[A-Za-z0-9_-]*[ \t]*\n(.*?)\n?```\s*\Z", re.DOTALL)


@dataclass(frozen=True)
class LineItem:
    """One invoice line."""

    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    kind: Kind = "item"


@dataclass(frozen=True)
class Invoice:
    """An extracted invoice; dates are ISO strings or ``date`` objects."""

    vendor_name: str | None
    vendor_tax_id: str | None
    invoice_number: str | None
    issue_date: str | date | None
    due_date: str | date | None
    currency: str | None
    line_items: Sequence[LineItem]
    subtotal: Decimal | None
    tax_total: Decimal | None
    total: Decimal | None
    prices_include_tax: bool = False
    is_credit_note: bool = False


@dataclass(frozen=True)
class ValidationIssue:
    """A validation finding."""

    code: str
    path: str
    message: str
    severity: Literal["error", "warning"]


def _invalid() -> InvoiceError:
    return InvoiceError("invalid_amount", "invalid amount")


def _decimal_index(body: str, forced: str | None) -> int | None:
    if forced is not None:
        if body.count(forced) > 1:
            raise _invalid()
        return body.find(forced) if forced in body else None
    last = max(body.rfind("."), body.rfind(","))
    if last < 0:
        return None
    sep = body[last]
    other = "," if sep == "." else "."
    if body.count(sep) > 1:
        if other in body:
            raise _invalid()
        return None
    only = other not in body and not any(g in body for g in _GROUP_CHARS)
    if len(body) - last - 1 == 3 and only:
        raise AmbiguousAmountError("amount with one separator and three digits is ambiguous")
    return last


def _group_digits(int_part: str) -> str:
    seps = {c for c in int_part if c not in _DIGITS}
    if not seps:
        return int_part
    if len(seps) > 1:
        raise _invalid()
    groups = int_part.split(seps.pop())
    if not all(g and all(c in _DIGITS for c in g) for g in groups):
        raise _invalid()
    if len(groups[0]) > 3 or any(len(g) != 3 for g in groups[1:]):
        raise _invalid()
    return "".join(groups)


def parse_amount(
    text: str | int | Decimal, *, decimal_separator: Literal[".", ","] | None = None
) -> Decimal:
    """Parse a monetary amount strictly.

    Raises:
        AmbiguousAmountError: for a lone separator followed by exactly three digits.
        InvoiceError: with code ``invalid_amount`` for anything else malformed.
    """
    if isinstance(text, bool):
        raise _invalid()
    if isinstance(text, int):
        return Decimal(text)
    if isinstance(text, Decimal):
        exp = text.as_tuple().exponent
        if not text.is_finite() or not isinstance(exp, int):
            raise _invalid()
        if text.adjusted() > 30 or exp < -30:
            raise _invalid()
        return text
    if not isinstance(text, str) or len(text) > MAX_AMOUNT_CHARS:
        raise _invalid()
    if decimal_separator not in (None, ".", ","):
        raise ValueError("decimal_separator must be '.', ',' or None")
    body = text.strip()
    negatives = 0
    currency = False
    changed = True
    while changed:
        changed = False
        body = body.strip()
        if len(body) >= 2 and body[0] == "(" and body[-1] == ")":
            body, negatives, changed = body[1:-1], negatives + 1, True
        elif body.startswith(("-", "\u2212")):
            body, negatives, changed = body[1:], negatives + 1, True
        elif body.endswith("-"):
            body, negatives, changed = body[:-1], negatives + 1, True
        elif not currency:
            if body and body[0] in _SYMBOLS:
                body, currency, changed = body[1:], True, True
            elif body and body[-1] in _SYMBOLS:
                body, currency, changed = body[:-1], True, True
            elif _ISO_START.match(body):
                body, currency, changed = body[3:], True, True
            elif _ISO_END.search(body):
                body, currency, changed = body[:-3], True, True
    if negatives > 1 or not body:
        raise _invalid()
    if body[0] not in _DIGITS or body[-1] not in _DIGITS:
        raise _invalid()
    if any(c not in _DIGITS + ".," + _GROUP_CHARS for c in body):
        raise _invalid()
    idx = _decimal_index(body, decimal_separator)
    frac = ""
    int_part = body
    if idx is not None:
        int_part, frac = body[:idx], body[idx + 1 :]
        if not frac or any(c not in _DIGITS for c in frac):
            raise _invalid()
    digits = _group_digits(int_part)
    value = Decimal(digits + ("." + frac if frac else ""))
    return -value if negatives else value


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def validate_invoice(
    invoice: Invoice, *, currency_table: Mapping[str, int] | None = None
) -> list[ValidationIssue]:
    """Check required fields, dates, currency and Decimal arithmetic."""
    table = ISO_4217_EXPONENTS if currency_table is None else currency_table
    issues: list[ValidationIssue] = []

    def add(code: str, path: str, message: str, severity: Literal["error", "warning"]) -> None:
        issues.append(ValidationIssue(code, path, message, severity))

    for name in ("vendor_name", "invoice_number", "issue_date", "currency"):
        value = getattr(invoice, name)
        if value is None or (isinstance(value, str) and not value.strip()):
            add("FIELD_MISSING", name, "required field is missing", "error")
    if not invoice.line_items:
        add("FIELD_MISSING", "line_items", "at least one line item is required", "error")
    if invoice.total is None:
        add("FIELD_MISSING", "total", "required field is missing", "error")

    exp = 2
    if invoice.currency:
        known = table.get(invoice.currency)
        if known is None:
            add("CURRENCY_UNKNOWN", "currency", "currency is not in the table", "error")
        else:
            exp = known
    unit = Decimal(1).scaleb(-exp)

    parsed: dict[str, date] = {}
    for name in ("issue_date", "due_date"):
        raw = getattr(invoice, name)
        if raw is None or raw == "":
            continue
        got = _as_date(raw)
        if got is None:
            add("DATE_INVALID", name, "date is not a valid ISO date", "error")
        else:
            parsed[name] = got
    if len(parsed) == 2 and parsed["due_date"] < parsed["issue_date"]:
        add("DUE_BEFORE_ISSUE", "due_date", "due date is before issue date", "error")

    lines = list(invoice.line_items)
    for i, line in enumerate(lines):
        path = f"line_items[{i}].amount"
        if abs(line.quantity * line.unit_price - line.amount) > unit:
            add("LINE_AMOUNT", path, "amount differs from quantity x unit_price", "error")
        if line.kind == "item" and line.amount < 0 and not invoice.is_credit_note:
            add("NEGATIVE_AMOUNT", path, "item amount is negative", "error")
    count = len(lines)

    if invoice.subtotal is None:
        add("SUBTOTAL", "subtotal", "subtotal missing; check skipped", "warning")
    elif abs(sum((ln.amount for ln in lines), Decimal(0)) - invoice.subtotal) > unit * count:
        add("SUBTOTAL", "subtotal", "subtotal differs from the sum of lines", "error")
    if invoice.tax_total is None:
        add("TOTAL", "tax_total", "tax_total missing; check skipped", "warning")

    total = invoice.total
    if total is not None:
        if total < 0 and not invoice.is_credit_note:
            add("NEGATIVE_AMOUNT", "total", "total is negative", "error")
        expected: Decimal | None = None
        if invoice.subtotal is not None:
            if invoice.prices_include_tax:
                expected = invoice.subtotal
            elif invoice.tax_total is not None:
                expected = invoice.subtotal + invoice.tax_total
        if expected is not None and abs(total - expected) > unit * (count + 1):
            add("TOTAL", "total", "total differs from subtotal and tax", "error")
        t_exp = total.as_tuple().exponent
        if isinstance(t_exp, int) and -t_exp > exp:
            add("PRECISION", "total", "total has more decimals than the currency allows", "warning")
    return issues


def invoice_to_dict(invoice: Invoice) -> dict[str, Any]:
    """Convert an invoice to a JSON-ready dict with amounts as strings."""

    def amt(v: Decimal | None) -> str | None:
        return None if v is None else str(v)

    def dt(v: str | date | None) -> str | None:
        return v if v is None or isinstance(v, str) else v.isoformat()

    return {
        "vendor_name": invoice.vendor_name,
        "vendor_tax_id": invoice.vendor_tax_id,
        "invoice_number": invoice.invoice_number,
        "issue_date": dt(invoice.issue_date),
        "due_date": dt(invoice.due_date),
        "currency": invoice.currency,
        "line_items": [
            {
                "description": ln.description,
                "quantity": str(ln.quantity),
                "unit_price": str(ln.unit_price),
                "amount": str(ln.amount),
                "kind": ln.kind,
            }
            for ln in invoice.line_items
        ],
        "subtotal": amt(invoice.subtotal),
        "tax_total": amt(invoice.tax_total),
        "total": amt(invoice.total),
        "prices_include_tax": invoice.prices_include_tax,
        "is_credit_note": invoice.is_credit_note,
    }


def _reject_constant(name: str) -> Any:
    raise ValueError("non-finite number")


def load_json(text: str) -> Any:
    """Parse JSON (one code fence stripped) with Decimal numbers, never floats."""
    if len(text) > MAX_JSON_CHARS:
        raise InvoiceError("input_too_large", "JSON input is too large")
    match = _FENCE.match(text)
    if match:
        text = match.group(1)
    try:
        return json.loads(
            text, parse_float=Decimal, parse_int=Decimal, parse_constant=_reject_constant
        )
    except (ValueError, RecursionError):
        raise InvoiceError("extraction_failed", "input is not valid JSON") from None


def _bad(path: str) -> InvoiceError:
    return InvoiceError("extraction_failed", f"invalid or missing field: {path}")


def _opt_str(d: dict[str, Any], key: str, path: str) -> str | None:
    v = d.get(key)
    if v is None:
        return None
    if not isinstance(v, str) or len(v) > MAX_FIELD_CHARS:
        raise _bad(path)
    return v


def _amount(d: dict[str, Any], key: str, path: str) -> Decimal | None:
    v = d.get(key)
    if v is None:
        return None
    try:
        return parse_amount(v)
    except InvoiceError:
        raise _bad(path) from None


def _required(d: dict[str, Any], key: str, path: str) -> Decimal:
    v = _amount(d, key, path)
    if v is None:
        raise _bad(path)
    return v


def _flag(d: dict[str, Any], key: str) -> bool:
    v = d.get(key, False)
    if not isinstance(v, bool):
        raise _bad(key)
    return v


def _line(raw: Any, index: int) -> LineItem:
    p = f"line_items[{index}]"
    if not isinstance(raw, dict):
        raise _bad(p)
    kind = raw.get("kind", "item")
    if kind not in _KINDS:
        raise _bad(f"{p}.kind")
    return LineItem(
        description=_opt_str(raw, "description", f"{p}.description") or "",
        quantity=_required(raw, "quantity", f"{p}.quantity"),
        unit_price=_required(raw, "unit_price", f"{p}.unit_price"),
        amount=_required(raw, "amount", f"{p}.amount"),
        kind=kind,
    )


def invoice_from_obj(obj: Any) -> Invoice:
    """Build an Invoice from a decoded JSON object, raising extraction_failed if malformed."""
    if not isinstance(obj, dict):
        raise _bad("invoice")
    raw_lines = obj.get("line_items")
    if raw_lines is None:
        raw_lines = []
    if not isinstance(raw_lines, list) or len(raw_lines) > MAX_LINES:
        raise _bad("line_items")
    return Invoice(
        vendor_name=_opt_str(obj, "vendor_name", "vendor_name"),
        vendor_tax_id=_opt_str(obj, "vendor_tax_id", "vendor_tax_id"),
        invoice_number=_opt_str(obj, "invoice_number", "invoice_number"),
        issue_date=_opt_str(obj, "issue_date", "issue_date"),
        due_date=_opt_str(obj, "due_date", "due_date"),
        currency=_opt_str(obj, "currency", "currency"),
        line_items=tuple(_line(raw, i) for i, raw in enumerate(raw_lines)),
        subtotal=_amount(obj, "subtotal", "subtotal"),
        tax_total=_amount(obj, "tax_total", "tax_total"),
        total=_amount(obj, "total", "total"),
        prices_include_tax=_flag(obj, "prices_include_tax"),
        is_credit_note=_flag(obj, "is_credit_note"),
    )
