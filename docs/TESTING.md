# Testing

## Running

```sh
uv run pytest --cov=invoice_extractor   # tests with coverage report
uv run python scripts/check.py      # every gate, as CI and the factory run it
```

## Policy

- Branch coverage of `src/invoice_extractor` must stay at or above 80 %; the gate fails below it.
- Tests exercise the public API (`import invoice_extractor`) and assert observable effects: return values, raised exceptions and their codes.
- Each bug fix starts with a failing test that reproduces it.
- Tests are deterministic: no network, no wall clock, no dependence on test order.

## Layout

`tests/test_<module>.py` mirrors each public module. Shared fixtures go in `tests/conftest.py`.

The spec's acceptance cases cover amount parsing, line and total tolerances per currency, currency and date checks, the repair loop with `RecordedLLM`, prompt escaping and absence of invoice text in logs, and CLI exit codes. The factory has not yet executed the test suite for this release; results are pending measurement.
