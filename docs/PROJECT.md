# Project record

## Objective

Extract invoices and receipts from text into validated JSON with Decimal arithmetic checks per ISO 4217 minor units and a bounded LLM repair loop. Strict amount parsing, Decimal validation to the currency minor unit, and targeted model repair give reliable structured data where LLM output alone may contain plausible but wrong totals.

## Scope

- In scope: the public API documented in [README.md](../README.md), the CLI `validate` and `extract --recorded` subcommands, typed and tested.
- Out of scope: live LLM clients or network calls, runtime dependencies, vendor-specific templates, and OCR or PDF parsing. Anything needing runtime dependencies or I/O beyond the CLI requires an accepted ADR.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 140203 / 300016 |
| Hours (human) | pending measurement |
| Cost (USD) | 1.5575 |

## Factory run u100 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | claude-sonnet-5-5 | yes | 2954 | 128000 | 0 | 4246 | 0.6434 |
| generation | claude-sonnet-5-5 | yes | 2954 | 128000 | 0 | 4246 | 0.6434 |
| generation | claude-sonnet-5-5 | yes | 2954 | 39227 | 0 | 4246 | 0.1995 |
| docs | claude-haiku-5-5 | no | 118603 | 4789 | 0 | 0 | 0.0713 |

Total: $1.5575. Prices: Anthropic list prices.
