# invoice-extractor

[![PyPI version](https://img.shields.io/pypi/v/trysac-invoice-extractor)](https://pypi.org/project/trysac-invoice-extractor/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-invoice-extractor)](LICENSE)
[![CI](https://github.com/Trysac/u100-invoice-extractor/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u100-invoice-extractor/actions/workflows/ci.yml)

Extract invoices and receipts from text into validated JSON with Decimal arithmetic checks per ISO 4217 minor units and a bounded LLM repair loop

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-invoice-extractor
# or
uv add trysac-invoice-extractor
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import invoice_extractor

# normalize() trims surrounding whitespace and lower-cases the text.
print(invoice_extractor.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    invoice_extractor.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
