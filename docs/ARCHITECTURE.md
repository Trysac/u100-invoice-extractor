# Architecture

## Purpose

`trysac-invoice-extractor` is a small, dependency-free Python library that extracts invoices and receipts from text into validated JSON, using Decimal arithmetic checks per ISO 4217 minor units and a bounded LLM repair loop.

## Shape

```text
caller code --> invoice_extractor (public API in __init__.py)
                    |
                    +-- core.py     amounts, data model, validation, strict JSON
                    +-- extract.py  bounded LLM extraction and repair loop
                    +-- llm.py      LLM port and test doubles (RecordedLLM, FakeLLM)
                    +-- errors.py   typed errors
                    +-- __main__.py CLI (validate, extract)
```

- **Public API**: the names listed in `__all__` of `src/invoice_extractor/__init__.py`.
- **Errors**: typed `InvoiceError` subclasses carry a stable `code`.
- **Side effects**: the CLI reads files; the library core does not perform I/O. Logging uses a `NullHandler` and never records invoice text.

## Quality contract

`scripts/check.py` is the single definition of the gates; see [TESTING.md](TESTING.md).

## Decisions

Architecture decisions are recorded in [decisions/](decisions/) as numbered ADRs.
