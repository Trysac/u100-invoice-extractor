"""Typed errors for invoice_extractor."""

from __future__ import annotations

from typing import Literal

ErrorCode = Literal["invalid_amount", "ambiguous_amount", "extraction_failed", "input_too_large"]


class InvoiceError(Exception):
    """Base error of the library; ``code`` is a stable machine-readable identifier."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message[:200])
        self.code: ErrorCode = code


class AmbiguousAmountError(InvoiceError):
    """Raised when a single separator followed by three digits cannot be classified."""

    def __init__(self, message: str) -> None:
        super().__init__("ambiguous_amount", message)
