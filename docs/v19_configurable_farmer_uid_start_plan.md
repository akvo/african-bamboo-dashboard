# v19 — Configurable Farmer UID Start

## Problem

The current `generate_next_farmer_uid()` always starts at `"00001"` when no farmers exist in the database. When migrating from a legacy system where farmer IDs already exist (e.g., the latest old ID is `AB00350`), the app needs to continue numbering from `351` onward to avoid collisions with imported historical data.

### Current Behavior

```python
# farmer_sync.py — generate_next_farmer_uid()
result = Farmer.objects.aggregate(
    max_uid=Max(Cast("uid", IntegerField()))
)
max_uid = result["max_uid"]
if max_uid is None:
    return "00001"          # ← always starts here
return str(max_uid + 1).zfill(5)
```

| Scenario | Current result | Expected result |
|---|---|---|
| Empty DB, no config | `"00001"` | `"00001"` (default) |
| Empty DB, `uid_start=351` | `"00001"` ← wrong | `"00351"` |
| Max UID is `"00400"`, `uid_start=351` | `"00401"` ✓ | `"00401"` ✓ |

The fix: `next_uid = max(max_existing_uid + 1, uid_start)`.

---

## Data Model Change

### FarmerFieldMapping — add `uid_start`

**File:** `backend/api/v1/v1_odk/models.py`

```python
class FarmerFieldMapping(models.Model):
    form = models.ForeignKey(
        FormMetadata,
        on_delete=models.CASCADE,
        related_name="farmer_field_mapping",
    )
    unique_fields = models.TextField(
        help_text=(
            "Comma-separated standardized field "
            "names used to identify unique farmers. "
            "Values joined with ' - ' for display."
        ),
    )
    values_fields = models.TextField(
        help_text=(
            "Comma-separated standardized field "
            "names to store as key-value pairs in "
            "Farmer.values. "
            "First field is used as display name."
        ),
    )
    uid_start = models.PositiveIntegerField(  # NEW
        default=1,
        help_text=(
            "Minimum starting UID number. New "
            "farmer UIDs will be "
            "max(max_existing + 1, uid_start). "
            "Use this to continue numbering from "
            "a legacy system "
            "(e.g., 351 to continue after "
            "AB00350)."
        ),
    )
```

**Why on `FarmerFieldMapping`:** This is per-form configuration, and the mapping already holds all farmer-related config for a form. A global setting would be too coarse if multiple forms ever need different starting points.

---

## Implementation Plan

### Phase 1: Migration

**File:** `backend/api/v1/v1_odk/migrations/XXXX_add_uid_start_to_farmerfieldmapping.py`

```python
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "v1_odk",
            "XXXX_previous_migration",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="farmerfieldmapping",
            name="uid_start",
            field=models.PositiveIntegerField(
                default=1,
                help_text=(
                    "Minimum starting UID number. "
                    "New farmer UIDs will be "
                    "max(max_existing + 1, "
                    "uid_start). "
                    "Use this to continue numbering "
                    "from a legacy system "
                    "(e.g., 351 to continue after "
                    "AB00350)."
                ),
            ),
        ),
    ]
```

Existing `FarmerFieldMapping` records get `uid_start=1` (default), preserving current behavior.

---

### Phase 2: Backend — Update UID generation

**File:** `backend/api/v1/v1_odk/utils/farmer_sync.py`

#### 2a. Modify `generate_next_farmer_uid()`

Add a `min_start` parameter that sets the floor for UID generation:

```python
def generate_next_farmer_uid(min_start=1):
    """Generate the next sequential farmer UID.

    Uses numeric Cast + Max to avoid lexicographic
    ordering issues with string UIDs (e.g. "99999"
    sorting after "100000").

    Args:
        min_start: Minimum UID number. The result
            will be at least this value. Use this
            to continue numbering from a legacy
            system (e.g., 351 to start after
            AB00350).

    Returns zero-padded string with minimum
    5 digits.

    Returns:
        str: e.g. "00001", "00042", "100000"
    """
    result = Farmer.objects.aggregate(
        max_uid=Max(
            Cast("uid", IntegerField())
        )
    )
    max_uid = result["max_uid"]
    if max_uid is None:
        return str(min_start).zfill(5)
    next_uid = max(max_uid + 1, min_start)
    return str(next_uid).zfill(5)
```

**Behavior table:**

| `max_uid` in DB | `min_start` | Result | Explanation |
|---|---|---|---|
| `None` (empty) | `1` | `"00001"` | Default, no legacy data |
| `None` (empty) | `351` | `"00351"` | Start after legacy AB00350 |
| `350` | `351` | `"00351"` | Legacy data imported, continue |
| `400` | `351` | `"00401"` | Already past start, increment |
| `None` | `1000` | `"01000"` | Large start, still 5-digit padded |

#### 2b. Update `sync_farmers_for_form()`

Read `uid_start` from the mapping and pass it through:

```python
def sync_farmers_for_form(form):
    mapping = FarmerFieldMapping.objects.filter(
        form=form
    ).first()
    if not mapping:
        logger.info(
            "No FarmerFieldMapping for form %s",
            form.asset_uid,
        )
        return {
            "created": 0,
            "updated": 0,
            "linked": 0,
        }

    unique_fields = [
        f.strip()
        for f in mapping.unique_fields.split(",")
        if f.strip()
    ]
    values_fields = [
        f.strip()
        for f in mapping.values_fields.split(",")
        if f.strip()
    ]
    uid_start = mapping.uid_start          # ← NEW

    option_map, type_map = build_option_lookup(form)

    created = 0
    updated = 0
    linked = 0

    submissions = form.submissions.select_related(
        "plot"
    ).all()

    for submission in submissions:
        raw_data = submission.raw_data or {}

        lookup_key = build_farmer_lookup_key(
            raw_data,
            unique_fields,
            option_map,
            type_map,
        )
        if not lookup_key:
            continue

        all_fields = list(
            dict.fromkeys(
                unique_fields + values_fields
            )
        )
        values = build_farmer_values(
            raw_data,
            all_fields,
            option_map,
            type_map,
        )

        try:
            farmer = Farmer.objects.get(
                lookup_key=lookup_key
            )
            farmer.values = values
            farmer.save(update_fields=["values"])
            updated += 1
        except Farmer.DoesNotExist:
            for attempt in range(3):
                uid = generate_next_farmer_uid(
                    min_start=uid_start,     # ← CHANGED
                )
                try:
                    farmer = (
                        Farmer.objects.create(
                            uid=uid,
                            lookup_key=lookup_key,
                            values=values,
                        )
                    )
                    created += 1
                    break
                except IntegrityError:
                    if attempt == 2:
                        raise
                    continue

        try:
            plot = submission.plot
        except Exception:
            plot = None

        if plot and plot.farmer_id != farmer.pk:
            plot.farmer = farmer
            plot.save(update_fields=["farmer"])
            linked += 1

    logger.info(
        "sync_farmers_for_form %s: "
        "created=%d updated=%d linked=%d",
        form.asset_uid,
        created,
        updated,
        linked,
    )
    return {
        "created": created,
        "updated": updated,
        "linked": linked,
    }
```

#### 2c. Update `update_farmer_for_submission()`

Read `uid_start` and pass to `_find_or_create_farmer()`:

```python
def update_farmer_for_submission(form, submission):
    mapping = FarmerFieldMapping.objects.filter(
        form=form
    ).first()
    if not mapping:
        return {
            "action": "no_mapping",
            "farmer_id": None,
        }

    unique_fields = [
        f.strip()
        for f in mapping.unique_fields.split(",")
        if f.strip()
    ]
    values_fields = [
        f.strip()
        for f in mapping.values_fields.split(",")
        if f.strip()
    ]
    uid_start = mapping.uid_start          # ← NEW

    # ... existing option_map, type_map,
    # new_lookup_key, new_values logic ...

    # In the "shared farmer — detach" branch
    # (line ~420):
    farmer = _find_or_create_farmer(
        new_lookup_key,
        new_values,
        min_start=uid_start,               # ← CHANGED
    )

    # In the "no existing farmer" branch
    # (line ~438):
    farmer = _find_or_create_farmer(
        new_lookup_key,
        new_values,
        min_start=uid_start,               # ← CHANGED
    )
```

#### 2d. Update `_find_or_create_farmer()`

Accept and forward `min_start`:

```python
def _find_or_create_farmer(
    lookup_key, values, min_start=1
):
    """Find a Farmer by lookup_key, or create one.

    Args:
        lookup_key: Unique farmer identifier string
        values: Dict of field name to resolved value
        min_start: Minimum UID number for new
            farmers

    Returns:
        Farmer instance
    """
    try:
        farmer = Farmer.objects.get(
            lookup_key=lookup_key
        )
        farmer.values = values
        farmer.save(update_fields=["values"])
        return farmer
    except Farmer.DoesNotExist:
        for attempt in range(3):
            uid = generate_next_farmer_uid(
                min_start=min_start,         # ← CHANGED
            )
            try:
                return Farmer.objects.create(
                    uid=uid,
                    lookup_key=lookup_key,
                    values=values,
                )
            except IntegrityError:
                if attempt == 2:
                    raise
                continue
```

---

### Phase 3: Backend — Management command `--clean` flag

**File:** `backend/api/v1/v1_odk/management/commands/sync_farmers.py`

Add a `--clean` flag that deletes existing Farmer records (and unlinks plots) before re-syncing. This enables a clean re-sync with the configured `uid_start`.

```python
from django.core.management.base import BaseCommand

from api.v1.v1_odk.models import (
    Farmer,
    FormMetadata,
    Plot,
)
from api.v1.v1_odk.utils.farmer_sync import (
    sync_farmers_for_form,
)


class Command(BaseCommand):
    help = (
        "Sync Farmer records from submissions "
        "using FarmerFieldMapping config"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--form",
            type=str,
            default=None,
            help="asset_uid of a specific form",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            default=False,
            help=(
                "Delete existing Farmer records "
                "and unlink plots before syncing. "
                "Use with --form to scope cleanup "
                "to a specific form's farmers."
            ),
        )

    def handle(self, *args, **options):
        form_uid = options["form"]
        clean = options["clean"]

        if form_uid:
            try:
                form = FormMetadata.objects.get(
                    asset_uid=form_uid
                )
            except FormMetadata.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(
                        f"Form {form_uid} not found"
                    )
                )
                return
            forms = [form]
        else:
            forms = FormMetadata.objects.all()

        if clean:
            deleted = self._clean_farmers(forms)
            self.stdout.write(
                self.style.WARNING(
                    f"Cleaned {deleted} farmer(s), "
                    f"unlinked their plots"
                )
            )

        total_created = 0
        total_updated = 0
        total_linked = 0

        for form in forms:
            result = sync_farmers_for_form(form)
            total_created += result["created"]
            total_updated += result["updated"]
            total_linked += result["linked"]
            self.stdout.write(
                f"  {form.asset_uid}: "
                f"created={result['created']} "
                f"updated={result['updated']} "
                f"linked={result['linked']}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Total: created={total_created} "
                f"updated={total_updated} "
                f"linked={total_linked}"
            )
        )

    def _clean_farmers(self, forms):
        """Delete Farmer records linked to the
        given forms' plots and unlink those plots.

        Only deletes farmers that are exclusively
        linked to plots from these forms. Shared
        farmers (linked to plots from other forms)
        are unlinked but not deleted.

        Returns:
            int: number of farmers deleted
        """
        form_ids = [f.pk for f in forms]

        # Find all farmers linked to plots
        # from these forms
        farmer_ids = set(
            Plot.objects.filter(
                form_id__in=form_ids,
                farmer__isnull=False,
            ).values_list(
                "farmer_id", flat=True
            )
        )

        if not farmer_ids:
            return 0

        # Unlink all plots from these forms
        Plot.objects.filter(
            form_id__in=form_ids,
            farmer__isnull=False,
        ).update(farmer=None)

        # Delete farmers that have no remaining
        # plot references (safe for shared farmers)
        orphaned = Farmer.objects.filter(
            pk__in=farmer_ids,
            plots__isnull=True,
        )
        deleted_count = orphaned.count()
        orphaned.delete()

        return deleted_count
```

**Usage:**

```bash
# Clean + re-sync a specific form (recommended)
python manage.py sync_farmers --form aXXXXXX --clean

# Clean + re-sync ALL forms
python manage.py sync_farmers --clean

# Normal sync (no cleanup, backward compatible)
python manage.py sync_farmers
python manage.py sync_farmers --form aXXXXXX
```

**Workflow for legacy migration:**

```bash
# 1. Set uid_start=351 via API
curl -X PUT http://localhost:8000/api/v1/odk/forms/aXXXXXX/farmer-field-mapping/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "unique_fields": ["First_Name", "Father_s_Name", "Grandfather_s_Name"],
    "values_fields": ["First_Name", "Father_s_Name", "Grandfather_s_Name", "age_of_farmer"],
    "uid_start": 351
  }'

# 2. Clean existing farmers and re-sync from scratch
python manage.py sync_farmers --form aXXXXXX --clean

# 3. Verify — first farmer should be AB00351
python manage.py shell -c "
from api.v1.v1_odk.models import Farmer
for f in Farmer.objects.order_by('uid')[:5]:
    print(f'AB{f.uid}  {f.lookup_key}')
"
```

---

### Phase 4: Backend — Update farmer-field-mapping endpoint

**File:** `backend/api/v1/v1_odk/views.py`

#### 4a. GET response — include `uid_start`

```python
def farmer_field_mapping(
    self, request, asset_uid=None
):
    form = self.get_object()
    if request.method == "GET":
        mapping = FarmerFieldMapping.objects.filter(
            form=form
        ).first()
        if not mapping:
            return Response(
                {
                    "unique_fields": [],
                    "values_fields": [],
                    "uid_start": 1,         # ← NEW
                }
            )
        return Response(
            {
                "unique_fields": [
                    f.strip()
                    for f in (
                        mapping.unique_fields
                        .split(",")
                    )
                    if f.strip()
                ],
                "values_fields": [
                    f.strip()
                    for f in (
                        mapping.values_fields
                        .split(",")
                    )
                    if f.strip()
                ],
                "uid_start": (              # ← NEW
                    mapping.uid_start
                ),
            }
        )
```

#### 4b. PUT request — accept `uid_start`

Add validation after existing `unique_fields` / `values_fields` validation:

```python
    # PUT — after existing validation:

    # Validate uid_start (optional, defaults to 1)
    raw_uid_start = request.data.get(
        "uid_start", None
    )
    uid_start = 1
    if raw_uid_start is not None:
        try:
            uid_start = int(raw_uid_start)
            if uid_start < 1:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {
                    "detail": (
                        "uid_start must be a "
                        "positive integer"
                    )
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

    mapping, _ = (
        FarmerFieldMapping.objects.update_or_create(
            form=form,
            defaults={
                "unique_fields": unique_str,
                "values_fields": (
                    values_str or unique_str
                ),
                "uid_start": uid_start,      # ← NEW
            },
        )
    )
    return Response(
        {
            "unique_fields": [
                f.strip()
                for f in (
                    mapping.unique_fields.split(",")
                )
                if f.strip()
            ],
            "values_fields": [
                f.strip()
                for f in (
                    mapping.values_fields.split(",")
                )
                if f.strip()
            ],
            "uid_start": mapping.uid_start,  # ← NEW
        }
    )
```

---

### Phase 5: Frontend — Update farmer-field-mapping UI

**File:** `frontend/src/app/dashboard/forms/page.js`

#### 5a. Add state for `uid_start`

```javascript
// After line 90 (farmerValuesFields state)
const [farmerUidStart, setFarmerUidStart] = useState(1);
```

#### 5b. Load `uid_start` from GET response

```javascript
// In handleConfigureClick(), after line 237-238:
setFarmerUniqueFields(
  farmerRes.data?.unique_fields || []
);
setFarmerValuesFields(
  farmerRes.data?.values_fields || []
);
setFarmerUidStart(                      // ← NEW
  farmerRes.data?.uid_start || 1
);
```

#### 5c. Include `uid_start` in PUT payload

```javascript
// In handleSaveMapping(), around line 280-289:
if (farmerUniqueFields.length > 0) {
  await api.put(
    `/v1/odk/forms/${configForm.asset_uid}`
    + `/farmer-field-mapping/`,
    {
      unique_fields: farmerUniqueFields,
      values_fields:
        farmerValuesFields.length > 0
          ? farmerValuesFields
          : farmerUniqueFields,
      uid_start: farmerUidStart,        // ← NEW
    },
  );
}
```

#### 5d. Add `uid_start` input to the Farmer Fields tab

Insert after the "Values fields" section (after line 1051):

```jsx
{/* Starting Farmer ID Number */}
<div className="space-y-2">
  <Label htmlFor="uid-start">
    Starting Farmer ID Number
  </Label>
  <Input
    id="uid-start"
    type="number"
    min={1}
    value={farmerUidStart}
    onChange={(e) =>
      setFarmerUidStart(
        Math.max(
          1,
          parseInt(e.target.value, 10) || 1
        )
      )
    }
    className="w-40"
    placeholder="1"
  />
  <p className="text-xs text-muted-foreground">
    Minimum starting number for new farmer
    IDs. Use this to continue from legacy
    data (e.g., enter 351 to start after
    AB00350). Only affects new farmers —
    existing IDs are never changed.
  </p>
</div>
```

#### 5e. Reset on error/close

```javascript
// In the catch block of handleConfigureClick()
// (line 240-244):
setFarmerUidStart(1);                   // ← NEW
```

---

### Phase 6: Tests

**File:** `backend/api/v1/v1_odk/tests/tests_farmer_sync.py`

#### 6a. Test `generate_next_farmer_uid()` with `min_start`

Add to existing `GenerateUidTest` class:

```python
@override_settings(USE_TZ=False, TEST_ENV=True)
class GenerateUidTest(TestCase):
    def test_first_farmer(self):
        uid = generate_next_farmer_uid()
        self.assertEqual(uid, "00001")

    def test_sequential(self):
        Farmer.objects.create(
            uid="00005",
            lookup_key="test-key-5",
        )
        uid = generate_next_farmer_uid()
        self.assertEqual(uid, "00006")

    def test_beyond_five_digits(self):
        Farmer.objects.create(
            uid="99999",
            lookup_key="test-key-99999",
        )
        uid = generate_next_farmer_uid()
        self.assertEqual(uid, "100000")

    # ── NEW TESTS ──

    def test_min_start_empty_db(self):
        """Empty DB with min_start=351
        returns '00351'."""
        uid = generate_next_farmer_uid(
            min_start=351
        )
        self.assertEqual(uid, "00351")

    def test_min_start_below_existing(self):
        """min_start below max existing UID
        is ignored — increments normally."""
        Farmer.objects.create(
            uid="00400",
            lookup_key="test-key-400",
        )
        uid = generate_next_farmer_uid(
            min_start=351
        )
        self.assertEqual(uid, "00401")

    def test_min_start_above_existing(self):
        """min_start above max existing UID
        wins — jumps to min_start."""
        Farmer.objects.create(
            uid="00100",
            lookup_key="test-key-100",
        )
        uid = generate_next_farmer_uid(
            min_start=351
        )
        self.assertEqual(uid, "00351")

    def test_min_start_equal_to_next(self):
        """min_start equals max+1 — no gap."""
        Farmer.objects.create(
            uid="00350",
            lookup_key="test-key-350",
        )
        uid = generate_next_farmer_uid(
            min_start=351
        )
        self.assertEqual(uid, "00351")

    def test_default_min_start_is_one(self):
        """Default min_start=1 preserves
        backward compatibility."""
        uid = generate_next_farmer_uid()
        self.assertEqual(uid, "00001")

    def test_large_min_start(self):
        """Large min_start still zero-pads
        to at least 5 digits."""
        uid = generate_next_farmer_uid(
            min_start=1000
        )
        self.assertEqual(uid, "01000")
```

#### 6b. Test sync uses `uid_start` from mapping

```python
@override_settings(USE_TZ=False, TEST_ENV=True)
class SyncFarmersUidStartTest(TestCase):
    def setUp(self):
        self.form = _create_form_with_questions()

    def test_sync_uses_uid_start(self):
        """sync_farmers_for_form creates farmers
        starting from mapping.uid_start."""
        FarmerFieldMapping.objects.create(
            form=self.form,
            unique_fields=(
                "First_Name,"
                "Father_s_Name,"
                "Grandfather_s_Name"
            ),
            values_fields="First_Name",
            uid_start=351,
        )
        _create_submission(
            self.form,
            "k001",
            {
                "First_Name": "Dara",
                "Father_s_Name": "Hora",
                "Grandfather_s_Name": "Daye",
            },
        )

        result = sync_farmers_for_form(self.form)
        self.assertEqual(result["created"], 1)

        farmer = Farmer.objects.first()
        self.assertEqual(farmer.uid, "00351")

    def test_sync_increments_past_uid_start(self):
        """After exceeding uid_start, normal
        increment continues."""
        FarmerFieldMapping.objects.create(
            form=self.form,
            unique_fields=(
                "First_Name,"
                "Father_s_Name,"
                "Grandfather_s_Name"
            ),
            values_fields="First_Name",
            uid_start=351,
        )
        # Pre-existing farmer above uid_start
        Farmer.objects.create(
            uid="00400",
            lookup_key="existing",
            values={},
        )
        _create_submission(
            self.form,
            "k001",
            {
                "First_Name": "New",
                "Father_s_Name": "Farmer",
                "Grandfather_s_Name": "Here",
            },
        )

        result = sync_farmers_for_form(self.form)
        self.assertEqual(result["created"], 1)

        new_farmer = Farmer.objects.get(
            lookup_key="New - Farmer - Here"
        )
        self.assertEqual(new_farmer.uid, "00401")

    def test_sync_default_uid_start(self):
        """Without uid_start, defaults to 1
        (backward compatible)."""
        FarmerFieldMapping.objects.create(
            form=self.form,
            unique_fields=(
                "First_Name,"
                "Father_s_Name,"
                "Grandfather_s_Name"
            ),
            values_fields="First_Name",
        )
        _create_submission(
            self.form,
            "k001",
            {
                "First_Name": "Dara",
                "Father_s_Name": "Hora",
                "Grandfather_s_Name": "Daye",
            },
        )

        sync_farmers_for_form(self.form)
        farmer = Farmer.objects.first()
        self.assertEqual(farmer.uid, "00001")
```

#### 6c. Test management command `--clean`

```python
@override_settings(USE_TZ=False, TEST_ENV=True)
class SyncFarmersCleanCommandTest(TestCase):
    def setUp(self):
        self.form = _create_form_with_questions()
        FarmerFieldMapping.objects.create(
            form=self.form,
            unique_fields=(
                "First_Name,"
                "Father_s_Name,"
                "Grandfather_s_Name"
            ),
            values_fields="First_Name",
            uid_start=351,
        )
        _create_submission(
            self.form,
            "k001",
            {
                "First_Name": "Dara",
                "Father_s_Name": "Hora",
                "Grandfather_s_Name": "Daye",
            },
        )

    def test_clean_deletes_and_resyncs(self):
        """--clean deletes existing farmers,
        then re-syncs with uid_start."""
        # Initial sync (starts at 351)
        out = StringIO()
        call_command(
            "sync_farmers",
            "--form", "test_form",
            stdout=out,
        )
        self.assertEqual(
            Farmer.objects.count(), 1
        )
        self.assertEqual(
            Farmer.objects.first().uid, "00351"
        )

        # Clean and re-sync
        out = StringIO()
        call_command(
            "sync_farmers",
            "--form", "test_form",
            "--clean",
            stdout=out,
        )
        output = out.getvalue()
        self.assertIn("Cleaned", output)
        self.assertIn("created=1", output)

        # Farmer re-created with uid_start
        self.assertEqual(
            Farmer.objects.count(), 1
        )
        farmer = Farmer.objects.first()
        self.assertEqual(farmer.uid, "00351")

    def test_clean_unlinks_plots(self):
        """--clean unlinks plots before deleting
        farmers."""
        call_command(
            "sync_farmers",
            "--form", "test_form",
            stdout=StringIO(),
        )
        plot = Plot.objects.first()
        self.assertIsNotNone(plot.farmer)

        # Clean
        call_command(
            "sync_farmers",
            "--form", "test_form",
            "--clean",
            stdout=StringIO(),
        )

        # Plot re-linked to new farmer
        plot.refresh_from_db()
        self.assertIsNotNone(plot.farmer)

    def test_clean_without_form_cleans_all(self):
        """--clean without --form cleans all
        forms' farmers."""
        call_command(
            "sync_farmers",
            stdout=StringIO(),
        )
        self.assertEqual(
            Farmer.objects.count(), 1
        )

        call_command(
            "sync_farmers",
            "--clean",
            stdout=StringIO(),
        )
        # Re-created after clean
        self.assertEqual(
            Farmer.objects.count(), 1
        )

    def test_clean_preserves_shared_farmers(self):
        """--clean with --form does NOT delete
        farmers shared with other forms."""
        # Create second form sharing a farmer
        form2 = FormMetadata.objects.create(
            asset_uid="other_form",
            name="Other Form",
        )
        call_command(
            "sync_farmers",
            "--form", "test_form",
            stdout=StringIO(),
        )
        farmer = Farmer.objects.first()

        # Manually link a plot from form2
        # to same farmer
        sub2 = Submission.objects.create(
            uuid="uuid-other",
            form=form2,
            kobo_id="k-other",
            submission_time=1700000000000,
            raw_data={},
        )
        plot2 = Plot.objects.create(
            form=form2,
            submission=sub2,
            farmer=farmer,
            region="R",
            sub_region="SR",
            created_at=1700000000000,
        )

        # Clean only test_form
        call_command(
            "sync_farmers",
            "--form", "test_form",
            "--clean",
            stdout=StringIO(),
        )

        # Farmer still exists (shared with form2)
        plot2.refresh_from_db()
        self.assertIsNotNone(plot2.farmer)
```

**File:** `backend/api/v1/v1_odk/tests/tests_forms_endpoint.py`

#### 6d. Test farmer-field-mapping endpoint with `uid_start`

```python
def test_farmer_mapping_get_uid_start_default(
    self,
):
    """GET returns uid_start=1 when no mapping."""
    res = self.client.get(
        self.farmer_mapping_url,
        **self.auth,
    )
    self.assertEqual(res.data["uid_start"], 1)

def test_farmer_mapping_put_uid_start(self):
    """PUT with uid_start=351 saves correctly."""
    res = self.client.put(
        self.farmer_mapping_url,
        {
            "unique_fields": ["First_Name"],
            "values_fields": ["First_Name"],
            "uid_start": 351,
        },
        format="json",
        **self.auth,
    )
    self.assertEqual(res.status_code, 200)
    self.assertEqual(res.data["uid_start"], 351)

    # Verify persistence
    res2 = self.client.get(
        self.farmer_mapping_url,
        **self.auth,
    )
    self.assertEqual(res2.data["uid_start"], 351)

def test_farmer_mapping_put_without_uid_start(
    self,
):
    """PUT without uid_start defaults to 1."""
    res = self.client.put(
        self.farmer_mapping_url,
        {
            "unique_fields": ["First_Name"],
            "values_fields": ["First_Name"],
        },
        format="json",
        **self.auth,
    )
    self.assertEqual(res.data["uid_start"], 1)

def test_farmer_mapping_put_invalid_uid_start(
    self,
):
    """PUT with uid_start=0 returns 400."""
    res = self.client.put(
        self.farmer_mapping_url,
        {
            "unique_fields": ["First_Name"],
            "values_fields": ["First_Name"],
            "uid_start": 0,
        },
        format="json",
        **self.auth,
    )
    self.assertEqual(
        res.status_code, 400
    )

def test_farmer_mapping_put_negative_uid_start(
    self,
):
    """PUT with uid_start=-5 returns 400."""
    res = self.client.put(
        self.farmer_mapping_url,
        {
            "unique_fields": ["First_Name"],
            "values_fields": ["First_Name"],
            "uid_start": -5,
        },
        format="json",
        **self.auth,
    )
    self.assertEqual(
        res.status_code, 400
    )

def test_farmer_mapping_put_string_uid_start(
    self,
):
    """PUT with uid_start='abc' returns 400."""
    res = self.client.put(
        self.farmer_mapping_url,
        {
            "unique_fields": ["First_Name"],
            "values_fields": ["First_Name"],
            "uid_start": "abc",
        },
        format="json",
        **self.auth,
    )
    self.assertEqual(
        res.status_code, 400
    )
```

---

## Files to Modify

| File | Change |
|---|---|
| `backend/api/v1/v1_odk/models.py` | Add `uid_start` field to `FarmerFieldMapping` |
| `backend/api/v1/v1_odk/migrations/XXXX_*.py` | New migration for `uid_start` |
| `backend/api/v1/v1_odk/utils/farmer_sync.py` | Add `min_start` param to `generate_next_farmer_uid()`, thread it through `sync_farmers_for_form()`, `update_farmer_for_submission()`, `_find_or_create_farmer()` |
| `backend/api/v1/v1_odk/views.py` | Include `uid_start` in farmer-field-mapping GET/PUT |
| `backend/api/v1/v1_odk/management/commands/sync_farmers.py` | Add `--clean` flag with scoped farmer cleanup |
| `frontend/src/app/dashboard/forms/page.js` | Add `farmerUidStart` state, input field in Farmer Fields tab, include in GET/PUT |
| `backend/api/v1/v1_odk/tests/tests_farmer_sync.py` | Tests for `min_start` and `--clean` flag |
| `backend/api/v1/v1_odk/tests/tests_forms_endpoint.py` | Tests for `uid_start` in farmer-field-mapping endpoint |

---

## What Stays Unchanged

- Farmer UID format: still zero-padded numeric strings (5+ digits)
- Display format: still `"AB"` + UID (e.g., `"AB00351"`)
- `PREFIX_FARM_ID` constant: unchanged
- Export and Telegram notification formatting: unchanged
- Plot-farmer linking logic: unchanged
- Farmer deduplication via `lookup_key`: unchanged
- Retry logic for IntegrityError: unchanged

---

## Sync Flow Diagram

```
POST /api/v1/odk/forms/{uid}/sync/
  │
  ├── Sync questions from Kobo
  ├── Upsert submissions
  ├── Create/update plots
  │
  └── async_task(sync_farmers_for_form, form)
        │
        ├── Read FarmerFieldMapping
        │     └── uid_start = mapping.uid_start     ← NEW
        │
        └── For each submission:
              ├── Build lookup_key from unique_fields
              ├── Farmer.objects.get(lookup_key=...)
              │     └── Found → update values
              │
              └── Not found → create:
                    └── generate_next_farmer_uid(
                          min_start=uid_start        ← NEW
                        )
                    └── max(max_existing + 1, uid_start)
```

```
python manage.py sync_farmers --form aXXX --clean
  │
  ├── --clean phase:
  │     ├── Find farmers linked to form's plots
  │     ├── Unlink plots (set farmer=None)
  │     └── Delete orphaned farmers
  │           (preserves shared farmers)
  │
  └── sync phase:
        └── sync_farmers_for_form(form)
              └── Uses mapping.uid_start
                    for new farmer UIDs
```

```
PUT /api/v1/odk/submissions/{id}/
  (field edit on farmer-related fields)
  │
  └── _resync_farmers_if_needed()
        │
        └── update_farmer_for_submission(form, sub)
              │
              ├── Read FarmerFieldMapping
              │     └── uid_start = mapping.uid_start   ← NEW
              │
              ├── existing farmer, key unchanged
              │     └── update values (no UID change)
              │
              ├── existing farmer, key changed
              │     ├── sole owner → rename in place
              │     └── shared → _find_or_create_farmer(
              │           ..., min_start=uid_start       ← NEW
              │         )
              │
              └── no farmer → _find_or_create_farmer(
                    ..., min_start=uid_start              ← NEW
                  )
```

---

## Verification

```bash
# Run migration
docker-compose exec backend \
  python manage.py makemigrations v1_odk
docker-compose exec backend \
  python manage.py migrate

# Run tests
docker-compose exec backend \
  python manage.py test api.v1.v1_odk.tests

# Lint
docker-compose exec backend \
  bash -c "black . && isort . && flake8"
```

Manual test:

```bash
# 1. Set uid_start=351 via UI or API
# 2. Clean and re-sync
docker-compose exec backend \
  python manage.py sync_farmers \
    --form aXXXXXX --clean

# 3. Verify first farmer starts at AB00351
docker-compose exec backend \
  python manage.py shell -c "
from api.v1.v1_odk.models import Farmer
for f in Farmer.objects.order_by('uid')[:5]:
    print(f'AB{f.uid}  {f.lookup_key}')
"
```
