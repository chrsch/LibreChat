"""
Collmex API client — handles all HTTP communication with the Collmex CSV API.

Protocol: POST semicolon-delimited CSV over HTTPS.
Auth: LOGIN line prepended to every request body.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx

from config import CollmexConfig
from utils.csv_utils import parse_csv_response, build_csv_line
from utils.formatting import (
    to_comma_float,
    to_collmex_upload_date,
    to_collmex_query_date,
    today_yyyymmdd,
    years_ago_yyyymmdd,
    clean_text,
)


# ─── Data classes ──────────────────────────────────────────────────

@dataclass
class Vendor:
    number: str
    name: str
    preferred_account: str | None


@dataclass
class Account:
    number: str
    name: str


@dataclass
class AccountHistoryEntry:
    account: str
    frequency: int
    percentage: float


@dataclass
class InvoiceUpload:
    vendor_number: str
    invoice_date: str  # YYYY-MM-DD
    invoice_number: str
    net_amount: float
    vat_amount: float
    expense_account: str
    booking_text: str = ""
    currency: str = "EUR"


@dataclass
class UploadResult:
    success: bool
    message: str
    records_uploaded: int


@dataclass
class BookingNumberResult:
    booking_number: str | None


# ─── Client ───────────────────────────────────────────────────────

class CollmexClient:
    def __init__(self, config: CollmexConfig) -> None:
        self.config = config
        self.base_url = (
            f"https://www.collmex.de/c.cmx?{config.customer_id},0,data_exchange"
        )
        self.login_line = f"LOGIN;{config.username};{config.password}"
        self._client = httpx.Client(timeout=config.api_timeout_ms / 1000)

    # ── low-level ──────────────────────────────────────────────────

    def _request(self, csv_body: str) -> str:
        body = f"{self.login_line}\n{csv_body}"
        resp = self._client.post(
            self.base_url,
            content=body.encode("utf-8"),
            headers={"Content-Type": "text/csv", "Accept": "text/csv"},
        )
        resp.raise_for_status()
        return resp.text

    @staticmethod
    def _parse_messages(
        rows: list[list[str]],
    ) -> dict:
        errors: list[str] = []
        info: list[str] = []
        success = True
        for row in rows:
            if row[0] != "MESSAGE":
                continue
            msg_type = row[1] if len(row) > 1 else ""
            text = (row[3] if len(row) > 3 else row[2]) if len(row) > 2 else ""
            if msg_type == "E":
                success = False
                errors.append(text)
            else:
                info.append(text)
        return {"success": success, "errors": errors, "info": info}

    # ── VENDOR_GET ─────────────────────────────────────────────────

    def fetch_vendors(self) -> list[Vendor]:
        csv = f"VENDOR_GET;;{self.config.company_nr}\n"
        text = self._request(csv)
        rows = parse_csv_response(text)
        vendors: list[Vendor] = []

        for row in rows:
            if row[0] != "CMXLIF" or len(row) <= 8:
                continue
            number = row[1]
            name = row[7]
            if not number or not name:
                continue

            preferred_account: str | None = None
            aufwandskonto = (row[35] if len(row) > 35 else "").strip()
            if aufwandskonto:
                parts = aufwandskonto.split()
                if parts[0] and parts[0].isdigit() and parts[0].startswith("4"):
                    preferred_account = parts[0]

            vendors.append(Vendor(number=number, name=name, preferred_account=preferred_account))

        return vendors

    # ── ACCDOC_GET: Chart of accounts ─────────────────────────────

    def fetch_account_chart(self) -> list[Account]:
        start_date = years_ago_yyyymmdd(self.config.account_history_years)
        end_date = today_yyyymmdd()
        csv = f"ACCDOC_GET;{self.config.company_nr};;;;;;;;;;;;;{start_date};{end_date}\n"

        text = self._request(csv)
        rows = parse_csv_response(text)

        seen: dict[str, str] = {}
        for row in rows:
            if row[0] != "ACCDOC" or len(row) <= 10:
                continue
            acc_number = row[8]
            acc_name = row[9]
            if acc_number and acc_name and acc_number not in seen:
                seen[acc_number] = acc_name

        return [Account(number=n, name=nm) for n, nm in seen.items()]

    # ── ACCDOC_GET: Vendor account history ────────────────────────

    def fetch_vendor_account_history(
        self, vendor_number: str, years_back: int = 2
    ) -> list[AccountHistoryEntry]:
        date_from = years_ago_yyyymmdd(years_back)
        date_to = today_yyyymmdd()
        csv = f"ACCDOC_GET;{self.config.company_nr};;;;;;;;;;;{date_from};{date_to}\n"

        text = self._request(csv)
        rows = parse_csv_response(text)

        # Group by booking number (index 3)
        booking_map: dict[str, list[list[str]]] = {}
        for row in rows:
            if row[0] != "ACCDOC" or len(row) <= 15:
                continue
            booking_no = (row[3] if len(row) > 3 else "").strip()
            if not booking_no:
                continue
            booking_map.setdefault(booking_no, []).append(row)

        account_counts: dict[str, int] = {}
        total_bookings = 0

        for records in booking_map.values():
            vendor_found = False
            expense_accounts: list[str] = []
            for row in records:
                v_num = (row[14] if len(row) > 14 else "").strip()
                account = (row[8] if len(row) > 8 else "").strip()
                if v_num == vendor_number:
                    vendor_found = True
                if account and account.isdigit() and account.startswith("4"):
                    expense_accounts.append(account)

            if vendor_found and expense_accounts:
                total_bookings += 1
                for acc in expense_accounts:
                    account_counts[acc] = account_counts.get(acc, 0) + 1

        if total_bookings == 0:
            return []

        entries = [
            AccountHistoryEntry(
                account=acc,
                frequency=freq,
                percentage=round((freq / total_bookings) * 100, 1),
            )
            for acc, freq in account_counts.items()
        ]
        entries.sort(key=lambda e: e.frequency, reverse=True)
        return entries

    # ── CMXLRN: Upload supplier invoices ──────────────────────────

    def upload_invoices(self, invoices: list[InvoiceUpload]) -> UploadResult:
        if not invoices:
            return UploadResult(success=False, message="No invoices to upload", records_uploaded=0)

        lines: list[str] = []
        for inv in invoices:
            date_str = to_collmex_upload_date(inv.invoice_date)
            booking_text = clean_text(inv.booking_text or f"Rechnung {inv.invoice_number}")
            record = build_csv_line([
                "CMXLRN",
                inv.vendor_number,
                self.config.company_nr,
                date_str,
                clean_text(inv.invoice_number),
                to_comma_float(inv.net_amount),
                to_comma_float(inv.vat_amount),
                "", "", "", "",  # Fields 8-11 empty
                inv.currency or self.config.default_currency,
                self.config.default_tax_code,
                0,  # Payment target
                booking_text,
                "",  # Field 16 empty
                inv.expense_account,
                "", "", "",  # Fields 18-20 empty
                "Importiert via LangChain Agent",
            ])
            lines.append(record)

        text = self._request("\n".join(lines) + "\n")
        rows = parse_csv_response(text)
        msgs = self._parse_messages(rows)

        if msgs["success"]:
            return UploadResult(
                success=True,
                message=f"Successfully uploaded {len(invoices)} invoice(s)",
                records_uploaded=len(invoices),
            )
        return UploadResult(
            success=False,
            message=f"Upload failed: {'; '.join(msgs['errors'])}",
            records_uploaded=0,
        )

    # ── ACCDOC_GET: Get booking number ────────────────────────────

    def get_booking_number(
        self, vendor_number: str, invoice_number: str, invoice_date: str
    ) -> BookingNumberResult:
        date_str = to_collmex_query_date(invoice_date)
        csv = f"ACCDOC_GET;{self.config.company_nr};;;;;;;;{invoice_number};;;;{date_str};{date_str}\n"

        text = self._request(csv)
        rows = parse_csv_response(text)

        current_year = date.today().year
        best_match: str | None = None
        best_year = 0

        for row in rows:
            if row[0] != "ACCDOC" or len(row) <= 15:
                continue
            year_str = (row[2] if len(row) > 2 else "").strip()
            booking_no = (row[3] if len(row) > 3 else "").strip()
            v_num = (row[14] if len(row) > 14 else "").strip()

            if not booking_no or not booking_no.isdigit():
                continue

            year = int(year_str) if year_str.isdigit() else 0

            if year == current_year and v_num == vendor_number:
                return BookingNumberResult(booking_number=booking_no)

            if year > best_year:
                best_year = year
                best_match = booking_no

        return BookingNumberResult(booking_number=best_match)
