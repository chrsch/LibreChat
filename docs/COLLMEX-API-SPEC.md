# Collmex API Specification

> Reverse-engineered from the `collmex-invoice-importer` Python tool.
> All details reflect the actual wire protocol observed in that tool's implementation.

---

## 1. Transport Layer

| Property | Value |
|---|---|
| **Base URL** | `https://www.collmex.de/c.cmx?{CUSTOMER_ID},0,data_exchange` |
| **Method** | `POST` |
| **Encoding** | UTF-8 |
| **Content-Type** | `text/csv` |
| **Accept** | `text/csv` |
| **Timeout** | 30 seconds (recommended) |
| **Auth** | First CSV line: `LOGIN;{username};{password}` |

Every request body is a semicolon-delimited CSV. The first line is always the `LOGIN` command. Subsequent lines are one or more command records. The response is also semicolon-delimited CSV.

### Example raw request

```
LOGIN;api_user;api_password
VENDOR_GET;;1
```

### Example raw response

```
CMXLIF;70001;...;Apple Inc.;...
CMXLIF;70002;...;Hetzner Online GmbH;...
MESSAGE;S;0;Datenabfrage erfolgreich. Es wurden 18 Datensätze abgefragt.;
```

---

## 2. Response Format

Every response ends with a `MESSAGE` record:

```
MESSAGE;{type};{code};{text};
```

| Type | Meaning |
|---|---|
| `S` | Success |
| `W` | Warning |
| `E` | Error |

- **type `S`**: Operation completed successfully
- **type `E`**: Error — the operation failed; `text` contains the error description
- Multiple `MESSAGE` lines may appear (e.g., one per record)

---

## 3. API Commands

### 3.1 VENDOR_GET — Fetch Vendors

Retrieves all supplier (vendor / Lieferant) master data.

**Request:**

```
VENDOR_GET;;{company_number}
```

| Field | Position | Value |
|---|---|---|
| Command | 1 | `VENDOR_GET` |
| Vendor number | 2 | Empty (all vendors) or specific number |
| Company number | 3 | `1` (default company) |

**Response record type:** `CMXLIF` (Collmex Lieferant = Vendor)

**Response field mapping (0-indexed):**

| Index | Field Name (German) | Field Name (English) | Example |
|---|---|---|---|
| 0 | Satzart | Record type | `CMXLIF` |
| 1 | Lieferantennummer | Vendor number | `70001` |
| 2–6 | (various) | (address fields) | — |
| 7 | Firma | Company name | `Apple Inc.` |
| 8–34 | (various) | (contact, bank, etc.) | — |
| 35 | Aufwandskonto | Preferred expense account | `4616` or `4920 Telefon` |

**Notes on field 35 (Aufwandskonto):**
- May be empty (no preferred account configured)
- May contain just the account number: `4920`
- May contain account number + name: `4920 Telefon`
- Only accounts starting with `4` (expense accounts) are valid
- Parse by splitting on whitespace and taking the first token

**Typical response size:** 15–20 vendor records.

---

### 3.2 ACCDOC_GET — Fetch Accounting Documents

The primary query command for accounting documents (bookings). Used for three different purposes depending on parameters.

**Request format (15 fields, semicolon-separated):**

```
ACCDOC_GET;{company};{year};{booking_no};{};{};{};{};{};{invoice_no};{};{};{};{date_from};{date_to}
```

| Position | Field | Description |
|---|---|---|
| 1 | Command | `ACCDOC_GET` |
| 2 | Firma (Company) | `1` |
| 3 | Geschäftsjahr (Year) | Empty or specific year |
| 4 | Buchungsnummer (Booking no.) | Empty or specific |
| 5–9 | (various filters) | Typically empty |
| 10 | Belegnummer (Invoice no.) | Invoice number filter |
| 11–13 | (various) | Typically empty |
| 14 | Datum von (Date from) | `YYYYMMDD` format |
| 15 | Datum bis (Date to) | `YYYYMMDD` format |

**Response record type:** `ACCDOC`

**Response field mapping (0-indexed):**

| Index | Field Name (German) | Field Name (English) | Example |
|---|---|---|---|
| 0 | Satzart | Record type | `ACCDOC` |
| 1 | Firma | Company | `1` |
| 2 | Geschäftsjahr | Fiscal year | `2024` |
| 3 | Buchungsnummer | Booking number | `157` |
| 4–7 | (various) | (booking metadata) | — |
| 8 | Kontonummer | Account number | `4616` |
| 9 | Kontoname | Account name | `Werbekosten` |
| 10–13 | (various) | (amount, tax fields) | — |
| 14 | Lieferantennummer | Vendor number | `70001` |
| 15+ | (various) | (additional fields) | — |

#### Use Case A: Fetch Chart of Accounts

Query all bookings over a 2-year range and extract unique account number/name pairs.

```
ACCDOC_GET;1;;;;;;;;;;;;;{start_date};{end_date}
```

- `start_date`: `YYYYMMDD` — 2 years ago (e.g., `20240101`)
- `end_date`: `YYYYMMDD` — today (e.g., `20260221`)

**Parsing logic:**
```
For each ACCDOC row where len(row) > 10:
  account_number = row[8]   # Kontonummer
  account_name   = row[9]   # Kontoname
  → Deduplicate by account_number
```

**Typical result:** 100–150 unique accounts.

**Account number ranges (German SKR03):**

| Range | Category | Examples |
|---|---|---|
| 1000–1999 | Assets (Anlagevermögen) | 1200 Forderungen |
| 3000–3999 | Revenue, tax, liabilities | 3770 USt 19% |
| 4000–4999 | Operating expenses (Aufwand) | 4616 Software, 4640 Internet |

**Common expense accounts (SKR03):**

| Account | German Name | English Name |
|---|---|---|
| 4616 | Werbekosten/Software | Software / Digital services |
| 4640 | Internet/Hosting | Internet / Hosting / Domains |
| 4800 | Werbekosten | Advertising / Marketing |
| 4806 | Wartung Software/Hardware | Software/Hardware maintenance |
| 4900 | Sonstige betr. Aufwendungen | Other general expenses |
| 4920 | Telefon | Telephone |
| 4930 | Bürobedarf | Office supplies |
| 4940 | Zeitschriften/Bücher | Books / Journals |
| 4964 | Buchführungssoftware | Bookkeeping software |

#### Use Case B: Fetch Vendor Account History

Query all bookings in a date range, then filter by vendor number to determine historical expense account usage.

```
ACCDOC_GET;1;;;;;;;;;;;{date_from};{date_to}
```

- `date_from`: `YYYYMMDD` — N years ago
- `date_to`: `YYYYMMDD` — today

**Parsing logic (grouped by booking number):**

```
1. Group all ACCDOC rows by row[3] (Buchungsnummer)
2. For each booking group:
   a. Check if any row has row[14] == target_vendor_number
   b. If yes, collect all row[8] values that start with '4' (expense accounts)
3. Count frequency of each expense account across all bookings
4. Sort by frequency descending
```

This approach groups multi-line bookings (a single invoice may have multiple ACCDOC lines — debit and credit entries) and correctly identifies which expense accounts are associated with a vendor's invoices.

**Typical result:** 1–5 unique expense accounts per vendor with frequency counts.

#### Use Case C: Get Booking Number for an Invoice

Query by specific invoice number and date to retrieve the Collmex-assigned booking number.

```
ACCDOC_GET;1;;;;;;;;{invoice_number};;;;{invoice_date};{invoice_date}
```

- `invoice_number`: The invoice number exactly as uploaded
- `invoice_date`: `YYYYMMDD` format — same date for both from and to

**Parsing logic:**

```
For each ACCDOC row:
  year           = row[2]   # Geschäftsjahr
  booking_number = row[3]   # Buchungsnummer
  vendor_number  = row[14]  # Lieferantennummer

  Prefer: year == current_year AND vendor == expected_vendor
  Fallback: highest year available
```

**Important:** After uploading an invoice, wait **≥ 2 seconds** before querying for the booking number. Collmex processing is not instantaneous.

---

### 3.3 CMXLRN — Upload Supplier Invoice

Creates supplier invoice bookings (Lieferantenrechnung) in Collmex.

**Request:** One `CMXLRN` line per invoice. Multiple invoices can be batched in a single request.

**Record format (21 fields):**

| Position | Field (German) | Field (English) | Format / Example |
|---|---|---|---|
| 1 | Satzart | Record type | `CMXLRN` |
| 2 | Lieferantennummer | Vendor number | `70001` |
| 3 | Firma | Company number | `1` |
| 4 | Rechnungsdatum | Invoice date | `DD.MM.YYYY` (e.g., `15.01.2024`) |
| 5 | Rechnungsnummer | Invoice number | `INV-2024-001` |
| 6 | Nettobetrag | Net amount | German decimal: `100,00` |
| 7 | Steuerbetrag | VAT amount | German decimal: `19,00` |
| 8–11 | (leer) | (empty) | `""` |
| 12 | Währung | Currency | `EUR` |
| 13 | (Steuerschlüssel) | Tax code | `1600` (19% VAT standard) |
| 14 | (Zahlungsziel) | Payment target | `0` |
| 15 | Buchungstext | Booking text | `Rechnung INV-001 Apple: MacBook (2499.00 EUR)` |
| 16 | (leer) | (empty) | `""` |
| 17 | Aufwandskonto | Expense account | `4616` |
| 18–20 | (leer) | (empty) | `""` |
| 21 | Bemerkung | Comment/note | `Importiert via script` |

**Amount formatting:**
- Use German decimal notation: comma as decimal separator (`100,00` not `100.00`)
- Net amount = total amount − VAT amount
- Format: `{value:.2f}` with `.` replaced by `,`

**Date formatting:**
- Upload format: `DD.MM.YYYY` (e.g., `15.01.2024`)
- Note: This differs from the query format which uses `YYYYMMDD`

**Booking text construction:**
```
Base: "Rechnung {invoice_number} {vendor_name}"
With items: "Rechnung {invoice_number} {vendor_name}: {item1} ({price1} EUR), {item2} ({price2} EUR)"
Items sorted by price ascending, only items with price > 0
```

**Tax code values:**

| Code | Meaning |
|---|---|
| `1600` | Standard 19% VAT (Umsatzsteuer) |

**CSV encoding:**
- Delimiter: `;` (semicolon)
- Quoting: `QUOTE_MINIMAL` (only quote fields containing semicolons or quotes)
- Encoding: UTF-8

**Response:** Standard `MESSAGE` record(s):
- `MESSAGE;S;...` on success
- `MESSAGE;E;{error_text}` on failure

---

## 4. Authentication

```
LOGIN;{username};{password}
```

- Always the **first line** of every request
- Credentials are the Collmex API user credentials (not the web login)
- The customer ID is part of the URL, not the login line

---

## 5. Error Handling

### API-Level Errors

Response contains `MESSAGE;E;{code};{text}`:

| Error | Typical Cause |
|---|---|
| Authentication failed | Wrong username/password |
| Invalid record format | Missing or extra fields in CSV |
| Unknown vendor | Vendor number not in master data |
| Duplicate invoice | Invoice number already exists for this vendor |

### HTTP-Level Errors

| Status | Meaning |
|---|---|
| 200 | Success (check MESSAGE record for actual result) |
| 401 | Authentication failure at HTTP level |
| 500 | Server error |

**Important:** HTTP 200 does not guarantee success. Always parse the `MESSAGE` record.

---

## 6. Data Flow: Invoice Booking Chain

The complete chain for creating a booking from an invoice:

```
┌──────────────────────────────────────────────────────────────────┐
│ Step 1: VENDOR_GET → Vendor list (number, name, pref. account)  │
│         Used for: vendor matching, preferred account lookup      │
└──────────────┬───────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────────┐
│ Step 2: ACCDOC_GET (2-year range) → Chart of Accounts           │
│         Used for: account validation, name display               │
└──────────────┬───────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────────┐
│ Step 3: ACCDOC_GET (per vendor) → Account History               │
│         Used for: historical account selection (priority #1)     │
│         Groups by booking number, filters by vendor, counts 4xxx │
└──────────────┬───────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────────┐
│ Step 4: Account Selection (5-level priority)                     │
│         1. Historical account (from step 3)                      │
│         2. Vendor preferred account (from step 1, field 35)      │
│         3. AI suggestion (from LLM analysis)                     │
│         4. Static rules (keyword → account mapping)              │
│         5. Default: 4900                                         │
└──────────────┬───────────────────────────────────────────────────┘
               │
┌──────────────▼───────────────────────────────────────────────────┐
│ Step 5: CMXLRN upload → Create booking in Collmex               │
│         Batch: multiple invoices in one request                  │
│         Amounts in German comma format, date DD.MM.YYYY          │
└──────────────┬───────────────────────────────────────────────────┘
               │ wait ≥ 2 seconds
┌──────────────▼───────────────────────────────────────────────────┐
│ Step 6: ACCDOC_GET (by invoice no. + date) → Booking Number     │
│         Matches: current year + vendor number                    │
│         Fallback: highest year available                         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. Timing & Rate Limiting

| Operation | Typical Duration | Recommended Delay |
|---|---|---|
| VENDOR_GET | < 1s | — |
| ACCDOC_GET (chart) | 1–3s | — |
| ACCDOC_GET (history) | 1–2s per vendor | — |
| CMXLRN upload | 1–2s | — |
| ACCDOC_GET (booking no.) | < 1s | **Wait ≥ 2s after upload** |
| Between booking queries | — | 0.5s delay between queries |

No explicit rate limits documented, but sequential queries with small delays are recommended for reliability.

---

## 8. Static Vendor → Account Mapping (Fallback)

Used when no historical data or vendor preferences are available:

| Vendor Keyword | Account | Category |
|---|---|---|
| apple | 4616 | Software/Digital |
| jetbrains | 4616 | Software/Digital |
| github | 4616 | Software/Digital |
| openai | 4616 | Software/Digital |
| udemy | 4616 | Software/Digital |
| leetcode | 4616 | Software/Digital |
| hetzner | 4640 | Internet/Hosting |
| manitu | 4640 | Internet/Hosting |
| uptimerobot | 4640 | Internet/Hosting |
| signal | 4640 | Internet/Hosting |
| posteo | 4640 | Internet/Hosting |
| collmex | 4964 | Bookkeeping software |
| nzz | 4940 | Books/Journals |
| congstar | 4920 | Telephone |
| drillisch | 4920 | Telephone |
