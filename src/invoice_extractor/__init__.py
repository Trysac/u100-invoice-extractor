"""Extract invoices from text into validated JSON with Decimal arithmetic checks."""

from __future__ import annotations

from .core import (
    ISO_4217_EXPONENTS,
    Invoice,
    LineItem,
    ValidationIssue,
    invoice_to_dict,
    parse_amount,
    validate_invoice,
)
from .errors import AmbiguousAmountError, InvoiceError
from .extract import AttemptRecord, ExtractionResult, extract_invoice
from .llm import FakeLLM, LLMPort, Message, RecordedLLM, RecordingExhaustedError

__all__ = [
    "ISO_4217_EXPONENTS",
    "AmbiguousAmountError",
    "AttemptRecord",
    "ExtractionResult",
    "FakeLLM",
    "Invoice",
    "InvoiceError",
    "LLMPort",
    "LineItem",
    "Message",
    "RecordedLLM",
    "RecordingExhaustedError",
    "ValidationIssue",
    "__version__",
    "extract_invoice",
    "invoice_to_dict",
    "parse_amount",
    "validate_invoice",
]

__version__ = "0.1.0"
