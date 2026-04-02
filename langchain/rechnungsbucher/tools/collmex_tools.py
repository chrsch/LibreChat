"""
LangChain tool wrappers for the Collmex accounting API.

Each tool mirrors the corresponding MCP tool from the Collmex-Invoices MCP server.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from clients.collmex import CollmexClient, InvoiceUpload
from config import CollmexConfig


# Module-level client — initialised by init_collmex_tools()
_client: CollmexClient | None = None
_config: CollmexConfig | None = None


def init_collmex_tools(config: CollmexConfig) -> None:
    """Initialise the module-level Collmex client. Must be called before using tools."""
    global _client, _config
    _config = config
    _client = CollmexClient(config)


def _get_client() -> CollmexClient:
    if _client is None:
        raise RuntimeError("Collmex tools not initialised. Call init_collmex_tools() first.")
    return _client


def _get_config() -> CollmexConfig:
    if _config is None:
        raise RuntimeError("Collmex tools not initialised. Call init_collmex_tools() first.")
    return _config


# ─── Tools ─────────────────────────────────────────────────────────


@tool
def collmex_get_vendors() -> str:
    """Retrieve all vendor (supplier) master data from Collmex.

    Returns vendor numbers, company names, preferred expense accounts,
    and the unknown-vendor fallback number. Call this first to identify
    which vendor number belongs to an invoice vendor name.
    """
    client = _get_client()
    config = _get_config()
    vendors = client.fetch_vendors()
    result = {
        "vendors": [
            {"number": v.number, "name": v.name, "preferred_account": v.preferred_account}
            for v in vendors
        ],
        "unknown_vendor_number": config.unknown_vendor_number,
        "note": f'Use vendor number "{config.unknown_vendor_number}" for vendors not found in the list. Warn the user when using the unknown vendor.',
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


@tool
def collmex_get_account_chart() -> str:
    """Retrieve all expense and asset accounts (SKR03 chart of accounts) from Collmex.

    Returns account numbers and names. Use this to validate account numbers
    and display human-readable account names.
    """
    client = _get_client()
    accounts = client.fetch_account_chart()
    return json.dumps(
        [{"number": a.number, "name": a.name} for a in accounts],
        indent=2,
        ensure_ascii=False,
    )


class VendorAccountHistoryInput(BaseModel):
    vendor_number: str = Field(description='Collmex vendor number (e.g., "70001")')
    years_back: int = Field(default=2, description="Number of years of history to analyse (default: 2)")


@tool(args_schema=VendorAccountHistoryInput)
def collmex_get_vendor_account_history(vendor_number: str, years_back: int = 2) -> str:
    """Retrieve historical expense account usage for a specific Collmex vendor.

    Analyses past bookings to determine which expense accounts were used most frequently.
    The most-used account is typically the best choice (80%+ accuracy).
    Returns accounts sorted by frequency.
    """
    client = _get_client()
    history = client.fetch_vendor_account_history(vendor_number, years_back)
    if not history:
        return f"No account history found for vendor {vendor_number}. This vendor may be new or have no bookings in the past {years_back} years."
    return json.dumps(
        [{"account": h.account, "frequency": h.frequency, "percentage": h.percentage} for h in history],
        indent=2,
    )


# ─── select_account (pure logic, no API call) ─────────────────────

STATIC_RULES: dict[str, str] = {
    "apple": "4616",
    "jetbrains": "4616",
    "github": "4616",
    "openai": "4616",
    "udemy": "4616",
    "leetcode": "4616",
    "hetzner": "4640",
    "manitu": "4640",
    "uptimerobot": "4640",
    "signal": "4640",
    "posteo": "4640",
    "collmex": "4964",
    "nzz": "4940",
    "congstar": "4920",
    "drillisch": "4920",
}

DEFAULT_ACCOUNT = "4900"


class AccountHistoryItem(BaseModel):
    account: str
    frequency: int
    percentage: float | None = None


class SelectAccountInput(BaseModel):
    vendor_name: str = Field(description="Vendor/company name (for static rule matching)")
    vendor_preferred_account: Optional[str] = Field(default=None, description="Preferred expense account from vendor master data")
    account_history: Optional[list[AccountHistoryItem]] = Field(default=None, description="Historical account entries from collmex_get_vendor_account_history")
    ai_suggestion: Optional[str] = Field(default=None, description="Account number suggested by your analysis of the invoice content")


@tool(args_schema=SelectAccountInput)
def collmex_select_account(
    vendor_name: str,
    vendor_preferred_account: str | None = None,
    account_history: list[dict[str, Any]] | None = None,
    ai_suggestion: str | None = None,
) -> str:
    """Apply the 5-level account selection logic to determine the best expense account.

    Priority: 1) Historical usage, 2) Vendor preferred account,
    3) AI/LLM suggestion, 4) Static keyword rules, 5) Default 4900.
    Provide as many inputs as available for best results.
    """
    # 1. Historical
    if account_history:
        best = max(account_history, key=lambda x: x.frequency if hasattr(x, "frequency") else x.get("frequency", 0))
        freq = best.frequency if hasattr(best, "frequency") else best.get("frequency", 0)
        pct = best.percentage if hasattr(best, "percentage") else best.get("percentage", "?")
        acc = best.account if hasattr(best, "account") else best.get("account", "")
        return json.dumps(
            {"account": acc, "reason": f"Used {freq}x historically ({pct}% of bookings)", "source": "historical"},
            indent=2,
        )

    # 2. Vendor preferred
    if vendor_preferred_account:
        return json.dumps(
            {"account": vendor_preferred_account, "reason": "Vendor master data preferred account (Aufwandskonto)", "source": "vendor_preferred"},
            indent=2,
        )

    # 3. AI suggestion
    if ai_suggestion:
        return json.dumps(
            {"account": ai_suggestion, "reason": "LLM analysis of invoice content", "source": "ai"},
            indent=2,
        )

    # 4. Static rules
    name_lower = vendor_name.lower()
    for keyword, account in STATIC_RULES.items():
        if keyword in name_lower:
            return json.dumps(
                {"account": account, "reason": f'Static rule match for keyword "{keyword}"', "source": "static"},
                indent=2,
            )

    # 5. Default
    return json.dumps(
        {"account": DEFAULT_ACCOUNT, "reason": "No match found — using default general expense account", "source": "default"},
        indent=2,
    )


# ─── upload_invoice ────────────────────────────────────────────────

class InvoiceItem(BaseModel):
    vendor_number: str = Field(description='Collmex vendor number (e.g., "70001")')
    invoice_date: str = Field(description="Invoice date in YYYY-MM-DD format")
    invoice_number: str = Field(description="Invoice number as shown on the invoice")
    net_amount: float = Field(description="Net amount (excluding VAT) in EUR")
    vat_amount: float = Field(description="VAT amount in EUR")
    expense_account: str = Field(description='Expense account number (e.g., "4616")')
    booking_text: Optional[str] = Field(default=None, description="Booking text / description")
    currency: Optional[str] = Field(default=None, description='Currency code (default: EUR)')


class UploadInvoiceInput(BaseModel):
    invoices: list[InvoiceItem] = Field(description="Array of invoice objects to upload")


@tool(args_schema=UploadInvoiceInput)
def collmex_upload_invoice(invoices: list[dict[str, Any]]) -> str:
    """Upload one or more supplier invoices to Collmex (CMXLRN records).

    IMPORTANT: Always confirm with the user before calling this — uploads cannot be easily undone.
    The VAT rate is auto-determined by Collmex from net/VAT amounts.
    Do NOT pass any tax_code parameter.
    """
    client = _get_client()

    upload_items: list[InvoiceUpload] = []
    for inv_data in invoices:
        inv = inv_data if isinstance(inv_data, dict) else inv_data.__dict__
        missing = [f for f in ("vendor_number", "invoice_date", "invoice_number", "net_amount", "vat_amount", "expense_account") if not inv.get(f) and inv.get(f) != 0]
        if missing:
            return json.dumps(
                {"success": False, "message": f"Invoice {inv.get('invoice_number', '(unknown)')} missing: {', '.join(missing)}", "records_uploaded": 0},
                indent=2,
            )
        upload_items.append(
            InvoiceUpload(
                vendor_number=str(inv["vendor_number"]),
                invoice_date=str(inv["invoice_date"]),
                invoice_number=str(inv["invoice_number"]),
                net_amount=float(inv["net_amount"]),
                vat_amount=float(inv["vat_amount"]),
                expense_account=str(inv["expense_account"]),
                booking_text=inv.get("booking_text") or "",
                currency=inv.get("currency") or "EUR",
            )
        )

    result = client.upload_invoices(upload_items)
    return json.dumps(
        {"success": result.success, "message": result.message, "records_uploaded": result.records_uploaded},
        indent=2,
    )


# ─── get_booking_number ───────────────────────────────────────────

class GetBookingNumberInput(BaseModel):
    vendor_number: str = Field(description='Collmex vendor number (e.g., "70001")')
    invoice_number: str = Field(description="Invoice number exactly as uploaded")
    invoice_date: str = Field(description="Invoice date in YYYY-MM-DD format")


@tool(args_schema=GetBookingNumberInput)
def collmex_get_booking_number(vendor_number: str, invoice_number: str, invoice_date: str) -> str:
    """Retrieve the Collmex-assigned booking number for a recently uploaded invoice.

    Wait at least 2-3 seconds after uploading before calling this.
    """
    client = _get_client()
    result = client.get_booking_number(vendor_number, invoice_number, invoice_date)
    if result.booking_number:
        return json.dumps({"booking_number": result.booking_number, "found": True}, indent=2)
    return json.dumps(
        {"booking_number": None, "found": False, "hint": "Booking number not found. Try again after a few seconds."},
        indent=2,
    )


# ─── Export all tools ──────────────────────────────────────────────

ALL_COLLMEX_TOOLS = [
    collmex_get_vendors,
    collmex_get_account_chart,
    collmex_get_vendor_account_history,
    collmex_select_account,
    collmex_upload_invoice,
    collmex_get_booking_number,
]
