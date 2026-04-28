#!/usr/bin/env python3
"""
Grade student payment-processing APIs.

Expected files in the current working directory:
- urls.txt                student names + urls
- bank_test_accounts_all_strings.csv
- merchants.csv

This script:
1. Reads the student endpoints from urls.txt
2. Builds a set of good and bad requests
3. Sends each request to each student endpoint
4. Produces a readable report and a pass/fail summary

Usage:
    python grade_apis.py
    python grade_apis.py --urls urls.txt --report grading_report.txt

Notes:
- This script is intentionally fuzzy about response message matching.
- It accepts plain-text or JSON responses.
- It does not require exact wording, only close semantic matches.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterable

import requests


DEFAULT_TIMEOUT = 8


@dataclass
class StudentEndpoint:
    name: str
    url: str


@dataclass
class TestCase:
    key: str
    description: str
    payload_factory: Callable[[dict[str, str], dict[str, str]], dict[str, str]]
    expected_statuses: set[int] | None
    message_keywords_any: tuple[str, ...] = ()
    message_keywords_all: tuple[str, ...] = ()
    forbid_keywords: tuple[str, ...] = ()


@dataclass
class TestResult:
    testcase: TestCase
    passed: bool
    actual_status: int | None
    actual_message: str
    notes: str
    elapsed_seconds: float


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def clean_wrapped_text(value: str) -> str:
    value = (value or "").strip()
    value = value.strip(",")
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value.strip().strip(',').strip()


def parse_urls_file(path: Path) -> list[StudentEndpoint]:
    students: list[StudentEndpoint] = []

    with path.open(encoding="utf-8-sig", newline="") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            name = ""
            url = ""

            try:
                row = next(csv.reader([line], skipinitialspace=True))
            except Exception:
                row = []

            if len(row) >= 2:
                left = clean_wrapped_text(row[0])
                right = clean_wrapped_text(row[1])
                if right.lower().startswith("http"):
                    name, url = left, right

            if not url and "|" in line:
                left, right = line.split("|", 1)
                left = clean_wrapped_text(left)
                right = clean_wrapped_text(right)
                if right.lower().startswith("http"):
                    name, url = left, right

            if not url and "	" in line:
                left, right = line.split("	", 1)
                left = clean_wrapped_text(left)
                right = clean_wrapped_text(right)
                if right.lower().startswith("http"):
                    name, url = left, right

            if not url and re.search(r"https?://", line):
                match = re.search(r'(https?://[^\s"\']+)', line)
                if match:
                    url = clean_wrapped_text(match.group(1))
                    name = clean_wrapped_text(line.replace(match.group(1), "")) or url

            if not url:
                continue

            students.append(StudentEndpoint(
                name=clean_wrapped_text(name or url),
                url=clean_wrapped_text(url),
            ))

    return students

def format_card_number(card_num: str) -> str:
    digits = re.sub(r"\D+", "", card_num or "")
    if len(digits) == 16:
        return f"{digits[0:4]} {digits[4:8]} {digits[8:12]} {digits[12:16]}"
    return digits


def decimal_or_zero(value: str) -> Decimal:
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        return Decimal("0")


def choose_good_debit_account(accounts: list[dict[str, str]]) -> dict[str, str]:
    return max(accounts, key=lambda row: decimal_or_zero(row.get("balance", "0")))


def choose_good_credit_account(accounts: list[dict[str, str]]) -> dict[str, str]:
    def available_credit(row: dict[str, str]) -> Decimal:
        return decimal_or_zero(row.get("credit_limit", "0")) - decimal_or_zero(row.get("credit_used", "0"))
    return max(accounts, key=available_credit)


def choose_low_funds_debit_account(accounts: list[dict[str, str]]) -> dict[str, str]:
    positive = [row for row in accounts if decimal_or_zero(row.get("balance", "0")) > 0]
    if not positive:
        return accounts[0]
    return min(positive, key=lambda row: decimal_or_zero(row.get("balance", "0")))


def choose_low_credit_account(accounts: list[dict[str, str]]) -> dict[str, str]:
    def available_credit(row: dict[str, str]) -> Decimal:
        return decimal_or_zero(row.get("credit_limit", "0")) - decimal_or_zero(row.get("credit_used", "0"))
    return min(accounts, key=available_credit)


def build_inbound_payload(account: dict[str, str],
                          merchant: dict[str, str],
                          amount: str,
                          card_type: str,
                          timestamp: str | None = None) -> dict[str, str]:
    return {
        "bank": "Jeffs Bank",
        "card_holder": account["card_holder"],
        "cc_number": re.sub(r"\D+", "", account["card_num"] or ""),
        "exp_date": str(account["exp_date"]),
        "cvv": str(account["cvv"]),
        "card_zip": str(account["card_zip"]),
        "card_type": card_type,
        "merchant_name": merchant["Name"],
        "merchant_token": merchant["Token"],
        "amount": str(amount),
        "timestamp": timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def safe_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return None


def extract_message(response: requests.Response) -> str:
    text = response.text.strip()
    data = safe_json(response)

    if isinstance(data, dict):
        for key in ("message", "Message", "body", "result", "statusMessage", "detail", "error"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        try:
            return json.dumps(data, ensure_ascii=False)
        except Exception:
            pass

    return text


def normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def message_matches(message: str,
                    keywords_any: Iterable[str],
                    keywords_all: Iterable[str],
                    forbid_keywords: Iterable[str]) -> bool:
    normalized = normalize_text(message)

    if keywords_any:
        any_ok = any(normalize_text(k) in normalized for k in keywords_any)
    else:
        any_ok = True

    all_ok = all(normalize_text(k) in normalized for k in keywords_all)

    forbid_ok = all(normalize_text(k) not in normalized for k in forbid_keywords)

    return any_ok and all_ok and forbid_ok


def evaluate_response(testcase: TestCase,
                      status_code: int | None,
                      message: str) -> tuple[bool, str]:
    reasons: list[str] = []

    if testcase.expected_statuses is not None:
        if status_code not in testcase.expected_statuses:
            reasons.append(f"expected status in {sorted(testcase.expected_statuses)}, got {status_code}")

    if testcase.message_keywords_any or testcase.message_keywords_all or testcase.forbid_keywords:
        if not message_matches(message, testcase.message_keywords_any, testcase.message_keywords_all, testcase.forbid_keywords):
            reasons.append("message did not match expected meaning")

    return (len(reasons) == 0, "; ".join(reasons) if reasons else "ok")


def run_single_test(student: StudentEndpoint,
                    testcase: TestCase,
                    account: dict[str, str],
                    merchant: dict[str, str],
                    timeout: int) -> TestResult:
    payload = testcase.payload_factory(account, merchant)
    start = time.perf_counter()

    try:
        response = requests.post(student.url, json=payload, timeout=timeout)
        elapsed = time.perf_counter() - start
        message = extract_message(response)
        passed, notes = evaluate_response(testcase, response.status_code, message)
        return TestResult(
            testcase=testcase,
            passed=passed,
            actual_status=response.status_code,
            actual_message=message,
            notes=notes,
            elapsed_seconds=elapsed,
        )
    except requests.Timeout:
        elapsed = time.perf_counter() - start
        return TestResult(
            testcase=testcase,
            passed=False,
            actual_status=None,
            actual_message="",
            notes=f"request timed out after ~{elapsed:.2f}s",
            elapsed_seconds=elapsed,
        )
    except requests.RequestException as exc:
        elapsed = time.perf_counter() - start
        return TestResult(
            testcase=testcase,
            passed=False,
            actual_status=None,
            actual_message="",
            notes=f"request error: {exc}",
            elapsed_seconds=elapsed,
        )


def build_testcases() -> list[TestCase]:
    return [
        TestCase(
            key="good_debit",
            description="Good debit transaction",
            payload_factory=lambda acct, merch: build_inbound_payload(acct, merch, amount="4.25", card_type="debit"),
            expected_statuses={200},
            message_keywords_any=("accepted", "approve", "approved", "success", "ok", "processed"),
            forbid_keywords=("insufficient", "not authorized", "bad request", "verification", "do not honor"),
        ),
        TestCase(
            key="good_credit",
            description="Good credit transaction",
            payload_factory=lambda acct, merch: build_inbound_payload(acct, merch, amount="5.10", card_type="credit"),
            expected_statuses={200},
            message_keywords_any=("accepted", "approve", "approved", "success", "ok", "processed"),
            forbid_keywords=("insufficient", "not authorized", "bad request", "verification", "do not honor"),
        ),
        TestCase(
            key="insufficient_funds_debit",
            description="Debit transaction with insufficient funds",
            payload_factory=lambda acct, merch: build_inbound_payload(acct, merch, amount="999999.99", card_type="debit"),
            expected_statuses={200},
            message_keywords_any=("insufficient", "declined", "Declined"),
            message_keywords_all=("insufficient",),
        ),
        TestCase(
            key="insufficient_funds_credit",
            description="Credit transaction over limit",
            payload_factory=lambda acct, merch: build_inbound_payload(acct, merch, amount="999999.99", card_type="credit"),
            expected_statuses={200},
            message_keywords_any=("insufficient", "declined", "limit"),
        ),
        TestCase(
            key="bad_merchant_name",
            description="Bad merchant name",
            payload_factory=lambda acct, merch: {
                **build_inbound_payload(acct, merch, amount="4.25", card_type="debit"),
                "merchant_name": "Totally Fake Merchant",
            },
            expected_statuses={400, 401, 403},
            message_keywords_any=("not authorized", "declined", "bad request", "merchant"),
        ),
        TestCase(
            key="bad_merchant_token",
            description="Bad merchant token",
            payload_factory=lambda acct, merch: {
                **build_inbound_payload(acct, merch, amount="4.25", card_type="debit"),
                "merchant_token": "BADTOKEN",
            },
            expected_statuses={400, 401, 403},
            message_keywords_any=("not authorized", "declined", "bad request", "token", "merchant"),
        ),
        TestCase(
            key="bad_card_number",
            description="Bad account / card number",
            payload_factory=lambda acct, merch: {
                **build_inbound_payload(acct, merch, amount="4.25", card_type="debit"),
                "cc_number": "0000000000000000",
            },
            expected_statuses={404, 403, 400},
            message_keywords_any=("do not honor", "not found", "declined", "bad account", "card"),
        ),
        TestCase(
            key="bad_cvv",
            description="Bad CVV",
            payload_factory=lambda acct, merch: {
                **build_inbound_payload(acct, merch, amount="4.25", card_type="debit"),
                "cvv": "999",
            },
            expected_statuses={403, 400},
            message_keywords_any=("verification", "declined", "cvv", "forbidden", "card"),
        ),
        TestCase(
            key="bad_exp_date",
            description="Bad expiration date",
            payload_factory=lambda acct, merch: {
                **build_inbound_payload(acct, merch, amount="4.25", card_type="debit"),
                "exp_date": "01/99",
            },
            expected_statuses={403, 400},
            message_keywords_any=("verification", "declined", "expiration", "exp", "forbidden", "card"),
        ),
        TestCase(
            key="bad_zip",
            description="Bad ZIP code",
            payload_factory=lambda acct, merch: {
                **build_inbound_payload(acct, merch, amount="4.25", card_type="debit"),
                "card_zip": "00000",
            },
            expected_statuses={403, 400},
            message_keywords_any=("verification", "declined", "zip", "forbidden", "card"),
        ),
        TestCase(
            key="missing_cvv",
            description="Missing required field (cvv)",
            payload_factory=lambda acct, merch: {
                k: v for k, v in build_inbound_payload(acct, merch, amount="4.25", card_type="debit").items()
                if k != "cvv"
            },
            expected_statuses={400},
            message_keywords_any=("bad request", "missing", "declined", "malformed"),
        ),
        TestCase(
            key="missing_card_holder",
            description="Missing required field (card_holder)",
            payload_factory=lambda acct, merch: {
                k: v for k, v in build_inbound_payload(acct, merch, amount="4.25", card_type="debit").items()
                if k != "card_holder"
            },
            expected_statuses={400},
            message_keywords_any=("bad request", "missing", "declined", "malformed"),
        ),
        TestCase(
            key="malformed_amount",
            description="Malformed amount",
            payload_factory=lambda acct, merch: {
                **build_inbound_payload(acct, merch, amount="four dollars", card_type="debit"),
            },
            expected_statuses={400,403},
            message_keywords_any=("bad request", "declined", "malformed", "amount"),
        ),
        TestCase(
            key="bad_card_type",
            description="Invalid card_type",
            payload_factory=lambda acct, merch: {
                **build_inbound_payload(acct, merch, amount="4.25", card_type="banana"),
            },
            expected_statuses={400,403},
            message_keywords_any=("bad request", "declined", "malformed", "card", "txn"),
        ),
    ]


def build_student_report(student: StudentEndpoint,
                         results: list[TestResult]) -> str:
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    lines: list[str] = []
    divider = "=" * 90
    lines.append(divider)
    lines.append(f"STUDENT: {student.name}")
    lines.append(f"URL: {student.url}")
    lines.append(divider)

    for result in results:
        lines.append(f"[{'PASS' if result.passed else 'FAIL'}] {result.testcase.description}")
        lines.append(f"  Expected status: {sorted(result.testcase.expected_statuses) if result.testcase.expected_statuses is not None else 'any'}")
        lines.append(f"  Actual status:   {result.actual_status}")
        lines.append(f"  Message:         {result.actual_message or '<empty>'}")
        lines.append(f"  Notes:           {result.notes}")
        lines.append(f"  Time:            {result.elapsed_seconds:.2f}s")
        lines.append("-" * 90)

    lines.append(f"SUMMARY FOR {student.name}: {passed} passed, {failed} failed, {len(results)} total")
    lines.append("")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade student card-processing APIs")
    parser.add_argument("--urls", default="urls.txt", help="Path to urls.txt")
    parser.add_argument("--accounts", default="bank_test_accounts_all_strings.csv", help="Path to bank account CSV")
    parser.add_argument("--merchants", default="merchants.csv", help="Path to merchants CSV")
    parser.add_argument("--report", default="grading_report.txt", help="Output report filename")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Per-request timeout in seconds")
    args = parser.parse_args()

    urls_path = Path(args.urls)
    accounts_path = Path(args.accounts)
    merchants_path = Path(args.merchants)

    for path in (urls_path, accounts_path, merchants_path):
        if not path.exists():
            print(f"Missing required file: {path}", file=sys.stderr)
            return 1

    students = parse_urls_file(urls_path)
    if not students:
        print("No valid student URLs found in urls.txt", file=sys.stderr)
        return 1

    accounts = load_csv_rows(accounts_path)
    merchants = load_csv_rows(merchants_path)

    if not accounts:
        print("No accounts found in accounts csv", file=sys.stderr)
        return 1
    if not merchants:
        print("No merchants found in merchants csv", file=sys.stderr)
        return 1

    good_debit = choose_good_debit_account(accounts)
    good_credit = choose_good_credit_account(accounts)
    low_funds_debit = choose_low_funds_debit_account(accounts)
    low_credit = choose_low_credit_account(accounts)
    merchant = next((m for m in merchants if (m.get("Name") or "").strip().lower() == "tifinys creperie"), merchants[0])

    tests = build_testcases()

    all_student_reports: list[str] = []
    overall_lines: list[str] = []
    grand_pass = 0
    grand_fail = 0

    for student in students:
        results: list[TestResult] = []
        for testcase in tests:
            if testcase.key in {"good_credit", "insufficient_funds_credit"}:
                account = good_credit if testcase.key == "good_credit" else low_credit
            elif testcase.key in {"good_debit", "bad_merchant_name", "bad_merchant_token",
                                  "bad_card_number", "bad_cvv", "bad_exp_date",
                                  "bad_zip", "missing_cvv", "missing_card_holder",
                                  "malformed_amount", "bad_card_type"}:
                account = good_debit
            elif testcase.key == "insufficient_funds_debit":
                account = low_funds_debit
            else:
                account = good_debit

            result = run_single_test(student, testcase, account, merchant, timeout=args.timeout)
            results.append(result)

        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        grand_pass += passed
        grand_fail += failed

        all_student_reports.append(build_student_report(student, results))
        overall_lines.append(f"{student.name}: {passed}/{len(results)} passed ({failed} failed)")

    final_lines: list[str] = []
    final_lines.append("CARD API GRADING REPORT")
    final_lines.append(time.strftime("Generated: %Y-%m-%d %H:%M:%S", time.localtime()))
    final_lines.append("")
    final_lines.append("OVERALL SUMMARY")
    final_lines.append("-" * 90)
    final_lines.extend(overall_lines)
    final_lines.append("-" * 90)
    total_tests = grand_pass + grand_fail
    final_lines.append(f"Grand total: {grand_pass} passed, {grand_fail} failed, {total_tests} total")
    final_lines.append("")
    final_lines.append("DETAILS")
    final_lines.append("")
    final_lines.extend(all_student_reports)

    report_text = "\n".join(final_lines)
    Path(args.report).write_text(report_text, encoding="utf-8")
    print(report_text)
    print(f"\nSaved report to {args.report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
