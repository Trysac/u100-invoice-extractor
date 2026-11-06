"""Behavior tests for the public API of invoice_extractor."""

from __future__ import annotations

import pytest

import invoice_extractor


def test_normalize_trims_and_lowercases() -> None:
    assert invoice_extractor.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        invoice_extractor.normalize(value)


def test_version_is_semver() -> None:
    parts = invoice_extractor.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
