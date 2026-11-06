# Strict Decimal parsing and a bounded LLM repair loop

Status: accepted (generated, pending human review)

## Context

LLM extraction returns plausible but wrong totals, floats that lose cents and amounts in mixed number formats. Vendor-locked APIs and per-vendor templates are not acceptable.

## Decision

Parse amounts with a strict, ambiguity-rejecting parser. Decode JSON with Decimal only (never float). Validate arithmetic to ISO 4217 minor units with explicit tolerances. Drive the model through an LLMPort protocol in a loop of one attempt plus at most max_repairs repairs, sending at most 20 'path: message' lines per repair and keeping the attempt with the fewest errors (ties to the latest). Invoice text is wrapped in tags with the closing tag neutralised, and is never logged.

## Consequences

Ambiguous amounts such as '1.234' fail loudly instead of being guessed. Tolerances can accept rounding differences of a few minor units. The library has no runtime dependencies, and tests are deterministic via RecordedLLM. Callers supply the real LLM adapter and own its cost and failure handling.
