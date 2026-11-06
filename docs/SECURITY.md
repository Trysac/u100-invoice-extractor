# Security notes

## Threat model

`trysac-invoice-extractor` has no network access and no runtime dependencies. Its core performs no I/O; only the CLI reads files.

### Defended

- **Prompt injection from invoice text**: the invoice text is wrapped in `<invoice_text>` tags, a fixed system message says the content is data, and any `</invoice_text` in the text (any case) is rewritten to `&lt;`. This reduces but does not eliminate the risk.
- **Float precision loss and hostile numbers**: amounts are parsed as Decimal; JSON uses `parse_float=Decimal` and `parse_int=Decimal`; NaN and Infinity are rejected.
- **Oversized input**: amount strings are limited to 64 characters, JSON replies to 200,000 characters, text fields to 500 characters, line items to 1000, and extraction input to `max_input_chars` (default 100,000).
- **Unbounded retries**: the repair loop runs at most `1 + max_repairs` attempts.
- **Log leakage**: invoice text is never logged, and `AttemptRecord` holds only codes.
- **Unsafe deserialization**: no `eval`, `exec` or pickle; JSON is parsed with `json.loads`.

### Not defended

- A model that follows injected instructions anyway can still return wrong but schema-valid data; validation checks arithmetic and fields, not truthfulness.
- Deeply nested JSON is only stopped by `RecursionError`, which is mapped to `extraction_failed`.
- The library does not authenticate the LLM provider or protect API keys; callers supply the `LLMPort` implementation.
- Arithmetic checks depend on the caller-supplied or bundled ISO 4217 table, which is a snapshot (checked 2026-11-05).

## Publishing

Releases are published to PyPI with trusted publishing (OIDC) when available, never with a long-lived token stored in the repository.

To report a vulnerability, see [SECURITY.md](../SECURITY.md).
