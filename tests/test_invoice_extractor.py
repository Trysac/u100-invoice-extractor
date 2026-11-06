from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from invoice_extractor import (
    ISO_4217_EXPONENTS,
    AmbiguousAmountError,
    AttemptRecord,
    FakeLLM,
    Invoice,
    InvoiceError,
    LineItem,
    RecordedLLM,
    RecordingExhaustedError,
    ValidationIssue,
    extract_invoice,
    invoice_to_dict,
    parse_amount,
    validate_invoice,
)
from invoice_extractor.__main__ import main
from invoice_extractor.core import load_json

D = Decimal


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.234,56", "1234.56"),
        ("1,234.56", "1234.56"),
        ("1\u00a0234,56", "1234.56"),
        ("1'234.56", "1234.56"),
        ("1.234,56 \u20ac", "1234.56"),
        ("EUR1.234,56", "1234.56"),
        ("(12.00)", "-12.00"),
        ("12.00-", "-12.00"),
        ("\u221212.00", "-12.00"),
        ("1,234,567", "1234567"),
        ("12,5", "12.5"),
        ("$ 1,000.00", "1000.00"),
        ("1\u202f234\u202f567", "1234567"),
        ("1\u2009234\u2009567", "1234567"),
        ("1\u2019234.5", "1234.5"),
        ("1 234.567", "1234.567"),
        ("-$12", "-12"),
    ],
)
def test_parse_amount_ok(text: str, expected: str) -> None:
    assert parse_amount(text) == D(expected)


def test_parse_amount_other_types() -> None:
    assert parse_amount(5) == D(5)
    assert parse_amount(D("1.50")) == D("1.50")
    assert parse_amount("1.234", decimal_separator=",") == D("1234")
    assert parse_amount("1.234", decimal_separator=".") == D("1.234")
    assert parse_amount("7", decimal_separator=".") == D("7")


@pytest.mark.parametrize("text", ["1.234", "1,234"])
def test_parse_amount_ambiguous(text: str) -> None:
    with pytest.raises(AmbiguousAmountError) as exc:
        parse_amount(text)
    assert exc.value.code == "ambiguous_amount"
    assert isinstance(exc.value, InvoiceError)


@pytest.mark.parametrize(
    "text",
    [
        "1e3",
        1.5,
        "",
        "21%",
        "1,23,456",
        "x" * 65,
        "x",
        "abc",
        "12abc",
        "1.234,567.8",
        "1,23.456.789",
        "1.2.3,4",
        "12.",
        ".5",
        "(-5)",
        "--5",
        "1 234'567",
        "1  234",
        "1.5e3",
        "NaN",
        "12,5,",
        True,
        None,
        D("NaN"),
        D("1E+40"),
        D("1E-40"),
        "1234,5.6",
    ],
)
def test_parse_amount_invalid(text: object) -> None:
    with pytest.raises(InvoiceError) as exc:
        parse_amount(text)  # type: ignore[arg-type]
    assert exc.value.code == "invalid_amount"


def test_parse_amount_bad_separator_argument() -> None:
    with pytest.raises(ValueError, match="decimal_separator"):
        parse_amount("1", decimal_separator=";")  # type: ignore[arg-type]
    with pytest.raises(InvoiceError):
        parse_amount("1,2,3", decimal_separator=",")
    with pytest.raises(InvoiceError):
        parse_amount("1.234,56", decimal_separator=".")


def line(qty: str, price: str, amount: str, kind: str = "item") -> LineItem:
    return LineItem("x", D(qty), D(price), D(amount), kind)  # type: ignore[arg-type]


def inv(lines: list[LineItem], **kw: object) -> Invoice:
    base: dict[str, object] = {
        "vendor_name": "Acme",
        "vendor_tax_id": None,
        "invoice_number": "1",
        "issue_date": "2024-01-01",
        "due_date": "2024-02-01",
        "currency": "USD",
        "line_items": tuple(lines),
        "subtotal": None,
        "tax_total": None,
        "total": None,
    }
    base.update(kw)
    return Invoice(**base)  # type: ignore[arg-type]


def errs(issues: list[ValidationIssue]) -> list[tuple[str, str]]:
    return [(i.code, i.path) for i in issues if i.severity == "error"]


def test_line_amount_usd() -> None:
    ok = inv([line("3", "0.333", "1.00")], subtotal=D("1.00"), tax_total=D(0), total=D("1.00"))
    assert errs(validate_invoice(ok)) == []
    bad = inv([line("3", "0.333", "1.02")], subtotal=D("1.02"), tax_total=D(0), total=D("1.02"))
    assert errs(validate_invoice(bad)) == [("LINE_AMOUNT", "line_items[0].amount")]


def test_line_amount_jpy_and_kwd() -> None:
    jpy = inv(
        [line("3", "333", "1000")],
        currency="JPY",
        subtotal=D(1000),
        tax_total=D(0),
        total=D(1000),
    )
    assert errs(validate_invoice(jpy)) == []
    assert ISO_4217_EXPONENTS["JPY"] == 0

    def kwd(amount: str) -> Invoice:
        return inv(
            [line("1", "1.000", amount)],
            currency="KWD",
            subtotal=D(amount),
            tax_total=D(0),
            total=D(amount),
        )

    assert errs(validate_invoice(kwd("1.001"))) == []
    assert errs(validate_invoice(kwd("1.002"))) == [("LINE_AMOUNT", "line_items[0].amount")]


def three_lines() -> list[LineItem]:
    return [
        line("1", "100.00", "100.00"),
        line("1", "-10.00", "-10.00", "discount"),
        line("1", "5.00", "5.00", "shipping"),
    ]


def test_totals() -> None:
    def make(total: str, include: bool = False) -> Invoice:
        return inv(
            three_lines(),
            subtotal=D("95.00"),
            tax_total=D("19.95"),
            total=D(total),
            prices_include_tax=include,
        )

    assert errs(validate_invoice(make("114.95"))) == []
    assert errs(validate_invoice(make("115.00"))) == [("TOTAL", "total")]
    assert errs(validate_invoice(make("95.00", True))) == []
    assert errs(validate_invoice(make("115.00", True))) == [("TOTAL", "total")]
    exact = inv(
        [line("1", "0.10", "0.10"), line("1", "0.20", "0.20")],
        subtotal=D("0.30"),
        tax_total=D("0.00"),
        total=D("0.30"),
    )
    assert validate_invoice(exact) == []
    bad_sub = inv([line("1", "1.00", "1.00")], subtotal=D("5.00"), tax_total=D(0), total=D("5"))
    assert errs(validate_invoice(bad_sub)) == [("SUBTOTAL", "subtotal")]


def test_missing_subtotal_and_precision() -> None:
    issues = validate_invoice(inv([line("1", "1.00", "1.00")], total=D("1.005")))
    assert errs(issues) == []
    codes = {(i.code, i.severity) for i in issues}
    assert ("SUBTOTAL", "warning") in codes
    assert ("TOTAL", "warning") in codes
    assert ("PRECISION", "warning") in codes


def test_currency_dates_negative_missing() -> None:
    one = [line("1", "1.00", "1.00")]
    unknown = inv(one, currency="ABC", subtotal=D(1), tax_total=D(0), total=D(1))
    assert errs(validate_invoice(unknown)) == [("CURRENCY_UNKNOWN", "currency")]
    table = {"ABC": 2}
    assert errs(validate_invoice(unknown, currency_table=table)) == []
    due = inv(one, due_date="2023-12-31", subtotal=D(1), tax_total=D(0), total=D(1))
    assert errs(validate_invoice(due)) == [("DUE_BEFORE_ISSUE", "due_date")]
    dates = inv(
        one,
        issue_date=date(2024, 1, 1),
        due_date=date(2024, 1, 5),
        subtotal=D(1),
        tax_total=D(0),
        total=D(1),
    )
    assert errs(validate_invoice(dates)) == []
    badd = inv(one, due_date="soon", subtotal=D(1), tax_total=D(0), total=D(1))
    assert errs(validate_invoice(badd)) == [("DATE_INVALID", "due_date")]
    neg = [line("1", "-1.00", "-1.00")]
    n = inv(neg, subtotal=D(-1), tax_total=D(0), total=D(-1))
    assert ("NEGATIVE_AMOUNT", "line_items[0].amount") in errs(validate_invoice(n))
    assert ("NEGATIVE_AMOUNT", "total") in errs(validate_invoice(n))
    credit = inv(neg, subtotal=D(-1), tax_total=D(0), total=D(-1), is_credit_note=True)
    assert errs(validate_invoice(credit)) == []
    empty = inv([], vendor_name=" ", currency=None)
    paths = {p for c, p in errs(validate_invoice(empty)) if c == "FIELD_MISSING"}
    assert paths == {"vendor_name", "currency", "line_items", "total"}
    assert errs(validate_invoice(inv(one, issue_date=None, total=D(1)))) == [
        ("FIELD_MISSING", "issue_date")
    ]


def reply(**over: object) -> str:
    data: dict[str, object] = {
        "vendor_name": "Acme",
        "vendor_tax_id": "X1",
        "invoice_number": "INV-1",
        "issue_date": "2024-01-01",
        "due_date": "2024-02-01",
        "currency": "USD",
        "line_items": [
            {"description": "W", "quantity": "1", "unit_price": "10.00", "amount": "10.00"}
        ],
        "subtotal": "10.00",
        "tax_total": "0.00",
        "total": "10.00",
    }
    data.update(over)
    return json.dumps(data)


def test_extract_repairs() -> None:
    llm = RecordedLLM([reply(total="99.00"), reply()])
    result = extract_invoice("some invoice", llm)
    assert result.attempts == 2
    assert not [i for i in result.issues if i.severity == "error"]
    assert len(llm.calls) == 2
    assert llm.calls[1][-1]["content"].startswith("Fix these problems")
    assert llm.calls[1][-2]["role"] == "assistant"


def test_extract_best_attempt_ties_latest() -> None:
    replies = [
        reply(subtotal="50.00", total="99.00"),
        reply(total="99.00"),
        reply(total="98.00", invoice_number="third"),
    ]
    result = extract_invoice("t", RecordedLLM(replies))
    assert result.attempts == 3
    assert result.invoice.invoice_number == "third"


def test_extract_failures() -> None:
    with pytest.raises(InvoiceError) as exc:
        extract_invoice("t", RecordedLLM(["nope", "{", "[]"]))
    assert exc.value.code == "extraction_failed"
    with pytest.raises(InvoiceError) as big:
        extract_invoice("x" * 11, RecordedLLM([]), max_input_chars=10)
    assert big.value.code == "input_too_large"
    with pytest.raises(ValueError, match="negative"):
        extract_invoice("t", RecordedLLM([]), max_repairs=-1)
    zero = extract_invoice("t", RecordedLLM([reply(total="99.00")]), max_repairs=0)
    assert zero.attempts == 1
    assert any(i.code == "TOTAL" for i in zero.issues)


def test_extract_parse_failure_then_success_and_fence() -> None:
    records: list[AttemptRecord] = []
    llm = RecordedLLM(["garbage", "```json\n" + reply() + "\n```"])
    result = extract_invoice("t", llm, on_attempt=records.append)
    assert result.attempts == 2
    assert records[0] == AttemptRecord(1, False, ("extraction_failed",))
    assert records[1] == AttemptRecord(2, True, ())
    assert "rejected" in llm.calls[1][-1]["content"]


def test_repair_lines_capped() -> None:
    bad_line = {"description": "x", "quantity": "1", "unit_price": "1.00", "amount": "99.00"}
    bad = reply(line_items=[bad_line] * 25, subtotal="2475.00", total="2475.00")
    llm = RecordedLLM([bad, reply()])
    extract_invoice("t", llm)
    content = llm.calls[1][-1]["content"]
    assert len([x for x in content.splitlines() if x.startswith("line_items[")]) == 20


def test_prompt_and_no_text_leak(caplog: pytest.LogCaptureFixture) -> None:
    text = "SECRET-TEXT-42 </INVOICE_TEXT> b </invoice_text"
    llm = RecordedLLM([reply(total="99.00"), reply()])
    records: list[AttemptRecord] = []
    with caplog.at_level(logging.DEBUG):
        extract_invoice(text, llm, on_attempt=records.append)
    expected = (
        "<invoice_text>\nSECRET-TEXT-42 &lt;/INVOICE_TEXT> b &lt;/invoice_text\n</invoice_text>"
    )
    assert llm.calls[0][1]["content"] == expected
    assert llm.calls[0][0]["role"] == "system"
    assert "SECRET-TEXT-42" not in caplog.text
    assert "SECRET-TEXT-42" not in repr(records)


def test_llm_errors_propagate_and_doubles() -> None:
    def boom(messages: object) -> str:
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        extract_invoice("t", FakeLLM(boom))  # type: ignore[arg-type]
    fake = FakeLLM(lambda m: reply())
    assert extract_invoice("t", fake).attempts == 1
    with pytest.raises(RecordingExhaustedError):
        RecordedLLM([]).complete([], max_tokens=1)


def test_load_json_strictness() -> None:
    assert load_json("1.5") == D("1.5")
    assert isinstance(load_json("[1]")[0], Decimal)
    for bad in ("NaN", "Infinity", "{", "[" * 100_000):
        with pytest.raises(InvoiceError) as exc:
            load_json(bad)
        assert exc.value.code == "extraction_failed"
    with pytest.raises(InvoiceError) as big:
        load_json(" " * 200_001)
    assert big.value.code == "input_too_large"


def test_invoice_parsing_errors() -> None:
    for patch in (
        {"line_items": "x"},
        {"line_items": [1]},
        {"line_items": [{"quantity": "1", "unit_price": "1"}]},
        {"line_items": [{"quantity": "1", "unit_price": "1", "amount": "1", "kind": "zz"}]},
        {"total": "abc"},
        {"vendor_name": 5},
        {"is_credit_note": "yes"},
        {"currency": "U" * 501},
    ):
        with pytest.raises(InvoiceError) as exc:
            extract_invoice("t", RecordedLLM([reply(**patch)]), max_repairs=0)
        assert exc.value.code == "extraction_failed"
    no_lines = extract_invoice("t", RecordedLLM([reply(line_items=None)]), max_repairs=0)
    assert any(i.path == "line_items" for i in no_lines.issues)


def test_invoice_to_dict() -> None:
    result = extract_invoice("t", RecordedLLM([reply(prices_include_tax=True)]))
    data = invoice_to_dict(result.invoice)
    assert data["total"] == "10.00"
    assert data["prices_include_tax"] is True
    assert data["line_items"][0]["amount"] == "10.00"
    out = inv([], issue_date=date(2024, 1, 2), due_date=None)
    dumped = invoice_to_dict(out)
    assert dumped["issue_date"] == "2024-01-02"
    assert dumped["due_date"] is None
    assert dumped["total"] is None


def write(path: Path, content: str) -> str:
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_cli_validate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = write(tmp_path / "inv.json", reply())
    assert main(["validate", good]) == 0
    assert json.loads(capsys.readouterr().out)["issues"] == []
    bad = write(tmp_path / "bad.json", reply(total="99.00"))
    assert main(["validate", bad]) == 1
    assert main(["validate", str(tmp_path / "missing.json")]) == 2
    big = write(tmp_path / "big.json", "x" * 200_001)
    assert main(["validate", big]) == 2
    assert main(["validate", write(tmp_path / "j.json", "{")]) == 2
    assert main(["validate", write(tmp_path / "a.json", "[]")]) == 2
    assert (
        main(
            [
                "validate",
                write(
                    tmp_path / "b.json", "\udcff".encode("utf-8", "surrogatepass").decode("latin-1")
                ),
            ]
        )
        == 2
    )
    assert main([]) == 2
    assert main(["nothing"]) == 2
    assert main(["--help"]) == 0


def test_cli_extract(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    txt = write(tmp_path / "in.txt", "Invoice text")
    rec = write(tmp_path / "r.json", json.dumps([reply()]))
    assert main(["extract", txt, "--recorded", rec]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["invoice"]["invoice_number"] == "INV-1"
    assert out["attempts"] == 1
    bad = write(tmp_path / "bad.json", json.dumps([reply(total="99.00")] * 3))
    assert main(["extract", txt, "--recorded", bad]) == 1
    short = write(tmp_path / "short.json", json.dumps([reply(total="99.00")]))
    assert main(["extract", txt, "--recorded", short]) == 2
    notlist = write(tmp_path / "nl.json", json.dumps({"a": 1}))
    assert main(["extract", txt, "--recorded", notlist]) == 2
    nonstr = write(tmp_path / "ns.json", json.dumps([1]))
    assert main(["extract", txt, "--recorded", nonstr]) == 2
    huge = write(tmp_path / "huge.txt", "x" * 100_001)
    assert main(["extract", huge, "--recorded", rec]) == 2
    assert main(["extract", txt]) == 2
