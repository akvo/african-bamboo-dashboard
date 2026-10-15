# v30: Access to Finance Dashboard

> **Purpose**: Design for an "Access to finance" (A2F) tab on the dashboard,
> fed by an Excel snapshot of cooperatives, members, loans and parcels, hidden
> behind a runtime feature flag until the client signs it off.

---

## Feature: Access to Finance Dashboard Metrics

**Task ID**: [#60](https://github.com/akvo/african-bamboo-dashboard/issues/60)
**Author**: Zuhdil Herry Kurnia
**Date**: 2026-10-15
**Status**: Approved — implemented on branch `60-access-to-finance-dashboard`

---

## 1. Context

African Bamboo holds its lending data in Excel. The client wants the metrics
listed in `A2F_Metrics_AKVO.docx` (Reach, Volume, Loan terms, Portfolio
quality, Linked to other data) on the dashboard, filterable by region, woreda,
cooperative, gender, target group, youth and loan type, each view showing the
date of the data.

Inputs (from the Asana task):

- `AB_A2F_Dummy_Data_AKVO.xlsx` — invented data in the exact format real data
  will follow. Sheets: `README`, `cooperatives`, `members`, `loans`,
  `parcels`, `parameters`, `code_lists`. Row 1 is the header on every sheet.
- Two mockups on the issue: "Bars" and "Table" view, toggled per card.

Constraints from the issue:

- Each import **replaces** all A2F data. No history; it is a snapshot.
- The file name must not matter.
- Write-off uses `outstanding_balance`. Bamboo hectares come from
  `members.bamboo_area_ha`.
- Youth cut-off is pending client confirmation.
- Hidden in production until the flag is removed.
- Data inconsistencies are reported as-is; the client fixes the data.

## 2. Decisions

| Topic | Decision |
|---|---|
| Storage | One `A2FSnapshot` row holding each sheet as a JSON list |
| Import | `manage.py import_a2f <file.xlsx>`, atomic replace |
| Metric engine | Pure Python functions over the snapshot lists |
| Feature flag | Runtime backend env `A2F_ENABLED`, endpoint 404s when off |
| Tab scope | Tabs switch only the new middle section |
| Charts | Tailwind div bars, no chart library |
| Youth | `age <= YOUTH_MAX_AGE` (constant, `29`) at `data_as_of` |

**Why a JSON snapshot, not four models.** The data is small (rows per farmer
and loan), always replaced whole, and only read by one endpoint whose metrics
(medians, per-member means) are easier in Python than in the ORM anyway. One
model, one migration. Normalised models can come later if something needs to
query A2F rows directly.

**Why a runtime flag.** `deploy-prod.yml` promotes the image the test cluster
built, so a build-time `NEXT_PUBLIC_*` value cannot differ between test and
production. The backend reads `A2F_ENABLED` from the Vault-injected secret per
environment; the frontend learns the state from the metrics endpoint's 404.

## 3. Backend

New app `backend/api/v1/v1_a2f/`, registered in `INSTALLED_APPS` and mounted
at `api/v1/a2f/`.

### 3.1 Model

```python
class A2FSnapshot(models.Model):
    data_as_of = models.DateField()
    parameters = models.JSONField()     # {"data_as_of": "...", ...}
    cooperatives = models.JSONField()   # list of row dicts
    members = models.JSONField()
    loans = models.JSONField()
    parcels = models.JSONField()
    imported_at = models.DateTimeField(auto_now_add=True)
```

At most one row exists. Readers take `A2FSnapshot.objects.first()`.

### 3.2 Import command

`python manage.py import_a2f <path>`

1. Open with `openpyxl` (`data_only=True`). Already a dependency.
2. Require sheets `cooperatives`, `members`, `loans`, `parcels`,
   `parameters`. `README` and `code_lists` are ignored.
3. Require the header row of each data sheet to equal the expected column
   list exactly (names and order, per the workbook README). Extra or missing
   columns abort.
4. Skip fully blank rows. Convert per column type:
   - dates → ISO `YYYY-MM-DD` string (accept `datetime` or ISO text)
   - money, rates, areas, scores, counts → number
   - 0/1 flags → int
   - blank → `None`
   - everything else → stripped string
5. Read `parameters` as `{parameter: value}`; `data_as_of` is required.
6. Inside `transaction.atomic()`: delete existing snapshots, create the new
   one. Print row counts per sheet.

Any validation failure raises `CommandError` naming sheet, row and column;
nothing is written, so the previous snapshot stays live.

Columns not used by any metric (e.g. `polygon_geojson`, `green_flag`) are
still stored; the snapshot mirrors the file.

Running in a deployed environment: copy the file into the backend pod and run
the command there. The command's `help` text says so; no README section.

### 3.3 Metric definitions

Notation: `M` = filtered members, `L` = filtered loans, `A` = loans in `L`
with `loan_status == "Active"`, `borrowers` = distinct `member_id` in `L`.
Every ratio returns `null` on a zero denominator.

**KPI cards / Reach**

| Metric | Definition |
|---|---|
| Borrowers | `len(borrowers)`, "of `len(M)` enrolled members" |
| Enrolled members borrowing | `borrowers / M` |
| Borrowers who are women | borrowers with `gender == "F"` / borrowers |
| Borrowers who are youth | borrowers with youth age / borrowers |
| Coops with active loans | coops with a member holding a loan in `A` / coops in scope |

**Volume**

| Metric | Definition |
|---|---|
| Total disbursed | `sum(loan_amount_etb)` over `L`, with `len(L)` loans |
| Outstanding portfolio | `sum(outstanding_balance)` over `A` |
| Average / median loan | mean / median `loan_amount_etb` over `L` |
| Loan value per ha | total disbursed / `sum(bamboo_area_ha)` of borrowers |
| Disbursed still outstanding | outstanding portfolio / total disbursed |

**Loan terms**

| Metric | Definition |
|---|---|
| Average interest rate | `sum(amount * rate) / sum(amount)` over `L` |
| By collateral type | per `collateral_type`: loan count and amount over `L` |

**Portfolio quality**

| Metric | Definition |
|---|---|
| PAR30 | `sum(outstanding)` of `A` with `par_30_flag == 1` / outstanding portfolio |
| Written off | `sum(outstanding_balance)` of `L` with status `Written off` / total disbursed |
| Avg credit score | mean over active borrowers of each one's mean `credit_score` across their loans in `A` |

**Linked to other data**

| Metric | Definition |
|---|---|
| Borrowing rate by land title | for members in `M` with / without a parcel having `title_deed_no`: share who are borrowers |
| PAR30 by training | PAR30 over `A` split by member `training_completed` 1 / 0; `n` = active loans |
| Income change | mean `income_current - income_baseline` for borrowers / non-borrowers in `M` |
| Jobs per ETB 1M lent | `sum(jobs_created)` of borrowers / total disbursed × 1,000,000 |

Comparison groups (the four "Linked" pairs) with `n < 5` return `null`; the
UI shows "Not shown (n < 5)". Each group reports its `n`.

Youth is computed from `date_of_birth` and `data_as_of`, so the snapshot date,
not today, decides membership.

**Oracle.** The unfiltered dummy workbook must reproduce the mockup exactly:
29 of 36 borrowers, ETB 995,500 over 34 loans, ETB 492,475 outstanding,
PAR30 14.3%, 80.6% / 24.1% / 44.8% / 83.3% reach, average ETB 29,279, median
ETB 23,250, ETB 71,877/ha over 13.85 ha, 49.5% still outstanding, 12.99%
interest, collateral 9/252,500 · 9/343,500 · 8/171,500 · 8/228,000, written off
5.7% (ETB 56,420), credit score 689 over 24 borrowers, title 86.7% (15) vs
76.2% (21), PAR30 trained 10.7% (21) vs untrained 30.9% (5), income ETB 3,145
(29) vs ETB 3,429 (7), 28.1 jobs per ETB 1M (28 jobs).

### 3.4 Filters

| Param | Applies to | Match |
|---|---|---|
| `region` | members | `member.region` |
| `woreda` | members | `member.woreda` |
| `coop` | members | `member.coop_id` |
| `gender` | members | `M` / `F` |
| `target_group` | members | `SHF` / `YW` |
| `youth` | members | `yes` / `no` |
| `loan_type` | loans | `loan.loan_type` |

Member filters narrow `M`; `L` is then the loans of members in `M`.
`loan_type` narrows `L` only, so enrolled-member denominators stay and
"borrowers" become members holding a loan of that type. Coops in scope are
the coops matching `region`, `woreda` and `coop` (by the coop's own row).

### 3.5 Endpoint

`GET /api/v1/a2f/metrics/` — authenticated (project default auth).

- 404 when `settings.A2F_ENABLED` is false or no snapshot exists.
- Query params as in 3.4; blank values are ignored.

Response shape:

```json
{
  "data_as_of": "2026-09-30",
  "filter_options": {
    "regions": ["Oromia", "Sidama"],
    "woredas": {"Oromia": ["Ana Sora", "Bore"], "Sidama": ["Bursa", "Hula"]},
    "cooperatives": [{"value": "CO001", "label": "Hula Bamboo ..."}],
    "genders": ["F", "M"],
    "target_groups": ["SHF", "YW"],
    "loan_types": ["Asset finance", "..."]
  },
  "youth_max_age": 29,
  "reach": {"borrowers": 29, "members": 36, "...": "..."},
  "volume": {},
  "loan_terms": {},
  "portfolio_quality": {},
  "linked": {}
}
```

Filter options always come from the whole snapshot, not the filtered set.
Ratios are fractions (0–1); the frontend formats them.

`A2F_ENABLED` is read in `settings.py` like `TELEGRAM_ENABLED`
(`"true"` case-insensitive → `True`, default `False`).

## 4. Frontend

### 4.1 Page

`frontend/src/app/dashboard/page.js`:

- New hook `useA2FMetrics(filters)` → `{ data, isLoading, isEnabled }`.
  A 404 sets `isEnabled = false` and is not treated as an error.
- When `isEnabled`, render a `Tabs` bar ("Planting & carbon" /
  "Access to finance") between the top stat cards and the existing
  `FilterBar`. "Access to finance" renders `<A2FSection />`; "Planting &
  carbon" renders nothing extra. The top cards, filter bar and submissions
  table are untouched on both tabs.
- When disabled, nothing new renders; the page is identical to today.

### 4.2 Components (`frontend/src/components/a2f/`)

- `a2f-section.js` — "Data as of 30 Sep 2026", the seven filter `Select`s
  (woreda options depend on region; changing region clears woreda; youth
  label shows the cut-off), KPI cards, the five cards, and the format
  helpers (`ETB 995,500`, `14.3%`).
- `a2f-card.js` — card shell with a Chart/Table `StatTabs` toggle; each card
  passes a `chart` and a `table` render. Toggle state is per card. Also
  exports `Bar`: label, value, sub-label and a Tailwind bar (`width: pct%`).

Card contents follow the two mockups row for row. `null` values render "—"
or "Not shown (n < 5)" for comparison groups.

## 5. Configuration

- `.env.example`: `A2F_ENABLED=True` with a comment.
- `docker-compose.yml` backend: `A2F_ENABLED=${A2F_ENABLED:-False}`.
- Test cluster: set `A2F_ENABLED=True` in its Vault secret. Production:
  leave unset until sign-off. (Ops step, outside this repo.)

## 6. Data inconsistencies

Reported as recorded, nothing dropped or corrected:

- Inactive members holding active loans (M0019, M0030) still count as
  enrolled and as active borrowers.
- Land-certificate collateral on members without a titled parcel (5 loans)
  is shown under "Land certificate".

If the client spots these on the dashboard, they fix the source data.

## 7. Testing

Backend (`backend/api/v1/v1_a2f/tests/`):

- `fixtures/a2f_dummy.xlsx` — the dummy workbook (invented data).
- `tests_import_a2f_command.py` — imports the fixture; re-import replaces;
  wrong header, missing sheet, bad date and missing `data_as_of` each abort
  and leave the previous snapshot intact.
- `test_metrics.py` — unfiltered fixture reproduces every oracle number in
  3.3; one member filter, `loan_type` filter, youth filter, n < 5 suppression,
  zero-denominator `null`.
- `tests_a2f_metrics_endpoint.py` — 401 unauthenticated, 404 with flag off,
  404 with no snapshot, 200 shape with flag on, filter params applied.

Frontend (`frontend/__tests__/`):

- `a2f-section.test.js` — tabs hidden on 404; tabs shown and A2F section
  renders on 200; Chart/Table toggle switches one card only.

## 8. Out of scope

- Upload UI for the workbook (the issue asks for a script).
- History or trends over time (snapshot only).
- Euro display (`etb_per_eur` is stored in `parameters`, not shown).
- Validating coded values against `code_lists`.
