# invoice-extractor

[![PyPI version](https://img.shields.io/pypi/v/trysac-invoice-extractor)](https://pypi.org/project/trysac-invoice-extractor/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-invoice-extractor)](LICENSE)
[![CI](https://github.com/Trysac/u100-invoice-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u100-invoice-extractor/actions/workflows/ci.yml)

Extract invoices and receipts from text into validated JSON with Decimal arithmetic checks per ISO 4217 minor units and a bounded LLM repair loop.

## Problem

Invoice data entry is slow, and LLM extraction returns plausible but wrong totals, floats that lose cents and amounts in mixed number formats. Cloud document APIs are vendor-locked and template tools need rules per vendor. This library parses amounts strictly, validates arithmetic with Decimal to the currency's minor unit, and asks the model to repair specific errors, so callers receive structured data with explicit issues.

## Install

```sh
pip install trysac-invoice-extractor
# or
uv add trysac-invoice-extractor
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
from invoice_extractor import RecordedLLM, extract_invoice, parse_amount

print(parse_amount("1.234,56 €"))
reply = '{"vendor_name":"Acme","invoice_number":"1","issue_date":"2024-01-01","currency":"USD","line_items":[{"quantity":"1","unit_price":"10.00","amount":"10.00"}],"subtotal":"10.00","tax_total":"0.00","total":"10.00"}'
result = extract_invoice("Invoice 1 from Acme, total 10.00 USD", RecordedLLM([reply]))
print(result.invoice.total, result.attempts)
```

## API summary

- `parse_amount(text, *, decimal_separator=None) -> Decimal`: accepts at most 64 characters; one currency symbol or ISO code at either end; leading `-` or U+2212, trailing `-`, or parentheses for negatives; comma, dot, space, U+00A0, U+202F, U+2009, apostrophe and U+2019 as group separators. Floats, exponents and `%` are rejected.
- `validate_invoice(invoice, *, currency_table=None) -> list[ValidationIssue]`: checks required fields, dates, currency, and Decimal arithmetic. Issue codes: FIELD_MISSING, LINE_AMOUNT, SUBTOTAL, TOTAL, NEGATIVE_AMOUNT, DUE_BEFORE_ISSUE, CURRENCY_UNKNOWN, DATE_INVALID (errors) and PRECISION (warning).
- `extract_invoice(text, llm, *, max_repairs=2, max_input_chars=100_000, on_attempt=None) -> ExtractionResult`: one attempt plus up to `max_repairs` repairs; the best attempt has the fewest error issues.
- `invoice_to_dict(invoice) -> dict`: amounts as strings.
- Models: `LineItem` and `Invoice` (frozen dataclasses), `ValidationIssue`, `AttemptRecord`, `ExtractionResult`.
- LLM port: `LLMPort` protocol with `complete(messages, *, max_tokens)`; test doubles `RecordedLLM` and `FakeLLM`.
- Errors: `InvoiceError` with `code` in `invalid_amount`, `ambiguous_amount`, `extraction_failed`, `input_too_large`; `AmbiguousAmountError` subclasses it.
- Limits: 64 characters per amount, 200,000 characters per JSON reply, 500 characters per text field, 1000 line items, 20 repair lines per attempt.
- CLI: `invoice-extractor validate INVOICE.json` and `invoice-extractor extract FILE.txt --recorded REPLIES.json`. Exit 0 ok, 1 error issues, 2 usage, IO or parse error.

## Why not a cloud document API

Cloud document APIs are vendor-locked and template tools need rules per vendor; this library is vendor-neutral and runs locally on the text you provide.

## Security

See [docs/SECURITY.md](docs/SECURITY.md) for the threat model and its limits.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
