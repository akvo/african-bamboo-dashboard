# Plan: Replace Hardcoded Dashboard Stats with Real Data

## Context
The dashboard shows 3 stats cards with hardcoded values (5,023 / 80% / 1,000). We need a backend stats endpoint and a frontend hook to display real aggregated data per form, respecting all active filters.

---

## Step 1: Backend - Add `stats` action to `PlotViewSet`

**File:** `backend/api/v1/v1_odk/plot_views.py`

Add `Sum` to the existing `django.db.models` import:

```python
from django.db.models import (
    Count,
    Exists,
    OuterRef,
    Q,
    Sum,
)
```

Add the `stats` action method to `PlotViewSet` (after `filter_options`, before `export`):

```python
@extend_schema(
    tags=["Plots"],
    summary="Dashboard statistics",
)
@action(detail=False, methods=["get"])
def stats(self, request):
    """Aggregate stats for dashboard cards.

    Reuses get_queryset() so all filters
    (form_id, region, sub_region, date range,
    dynamic filters) are applied."""
    qs = self.get_queryset().order_by()

    pending_q = Q(
        submission__approval_status__isnull=True  # noqa: E501
    ) | Q(
        submission__approval_status=(
            ApprovalStatusTypes.PENDING
        )
    )

    result = qs.aggregate(
        total_plots=Count("id"),
        total_area_ha=Sum("area_ha"),
        approved_count=Count(
            "id",
            filter=Q(
                submission__approval_status=(
                    ApprovalStatusTypes.APPROVED
                )
            ),
        ),
        pending_count=Count(
            "id",
            filter=pending_q,
        ),
        pending_area_ha=Sum(
            "area_ha",
            filter=pending_q,
        ),
    )

    total = result["total_plots"] or 0
    approved = result["approved_count"] or 0
    approval_pct = (
        round(approved / total * 100, 1)
        if total > 0
        else 0
    )

    return Response(
        {
            "total_plots": total,
            "total_area_ha": round(
                result["total_area_ha"] or 0,
                2,
            ),
            "approval_percentage": (
                approval_pct
            ),
            "pending_count": (
                result["pending_count"] or 0
            ),
            "pending_area_ha": round(
                result["pending_area_ha"]
                or 0,
                2,
            ),
        }
    )
```

**Note:** Pending matches both `NULL` (database convention) and `PENDING=0` (constant) for safety.

**No URL changes needed** - DRF router auto-registers `@action` as `GET /api/v1/odk/plots/stats/`

---

## Step 2: Frontend - Create `useStats` hook

**File (new):** `frontend/src/hooks/useStats.js`

```javascript
"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import api from "@/lib/api";

export function useStats({
  formId,
  region,
  subRegion,
  startDate,
  endDate,
  dynamicFilters,
} = {}) {
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const dynamicKey = useMemo(
    () => JSON.stringify(dynamicFilters || {}),
    [dynamicFilters],
  );

  const fetchStats = useCallback(async () => {
    if (!formId) {
      setStats(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const params = { form_id: formId };
      if (region) {
        params.region = region;
      }
      if (subRegion) {
        params.sub_region = subRegion;
      }
      if (startDate) {
        params.start_date = startDate;
      }
      if (endDate) {
        params.end_date = endDate;
      }
      const parsed = JSON.parse(dynamicKey);
      for (const [key, val] of Object.entries(parsed)) {
        if (val) {
          params[`filter__${key}`] = val;
        }
      }
      const res = await api.get("/v1/odk/plots/stats/", { params });
      setStats(res.data);
    } catch {
      setStats(null);
    } finally {
      setIsLoading(false);
    }
  }, [formId, region, subRegion, startDate, endDate, dynamicKey]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return { stats, isLoading, refetch: fetchStats };
}
```

---

## Step 3: Frontend - Wire up dashboard page

**File:** `frontend/src/app/dashboard/page.js`

Add import:

```javascript
import { useStats } from "@/hooks/useStats";
```

Add hook call (after `useMapState`, before `startMs`/`endMs` declarations):

```javascript
const { stats } = useStats({
  formId: activeForm?.asset_uid,
  region,
  subRegion,
  startDate: startDate ? startDate.getTime() : null,
  endDate: endDate ? endDate.getTime() : null,
  dynamicFilters: dynamicValues,
});
```

### Card 1 - Total submissions (plot/ha toggle):

```jsx
<CardContent>
  <div className="text-3xl font-bold">
    {statsTab === "plot"
      ? (stats?.total_plots ?? 0).toLocaleString()
      : (stats?.total_area_ha ?? 0).toLocaleString()}
  </div>
  <p className="mt-1 text-sm text-muted-foreground">
    {statsTab === "plot"
      ? "Amount of plots mapped"
      : "Amount of hectares mapped"}
  </p>
</CardContent>
```

### Card 2 - Percentage approved:

```jsx
<CardContent>
  <div className="text-3xl font-bold">
    {stats?.approval_percentage ?? 0}%
  </div>
  <p className="mt-1 text-sm text-muted-foreground">
    Of plots out of 100%
  </p>
</CardContent>
```

### Card 3 - Items requiring review:

```jsx
<CardContent>
  <div className="text-3xl font-bold">
    {(stats?.pending_count ?? 0).toLocaleString()}
  </div>
  <p className="mt-1 text-sm text-muted-foreground">
    {(stats?.pending_area_ha ?? 0).toLocaleString()} hectares to map
  </p>
</CardContent>
```

---

## Step 4: Backend tests

**File (new):** `backend/api/v1/v1_odk/tests/tests_stats_endpoint.py`

Uses `OdkTestHelperMixin` for auth (consistent with existing test patterns). Submissions require `raw_data={}` and plots require `created_at` as both are non-null fields.

```python
from django.test import TestCase

from api.v1.v1_odk.constants import (
    ApprovalStatusTypes,
)
from api.v1.v1_odk.models import (
    FormMetadata,
    Plot,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)


class StatsEndpointTestCase(
    OdkTestHelperMixin, TestCase
):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="stats_form_001",
            name="Stats Test Form",
        )
        # 3 approved, 2 pending (NULL)
        for i in range(5):
            sub = Submission.objects.create(
                uuid=f"stats-sub-{i}",
                form=self.form,
                kobo_id=str(i),
                submission_time=(
                    1700000000000 + i
                ),
                raw_data={},
                approval_status=(
                    ApprovalStatusTypes.APPROVED
                    if i < 3
                    else None
                ),
            )
            Plot.objects.create(
                uuid=f"stats-plot-{i}",
                form=self.form,
                submission=sub,
                area_ha=10.0 + i,
                region="Region A",
                created_at=1700000000000 + i,
            )

    def test_stats_totals(self):
        url = "/api/v1/odk/plots/stats/"
        res = self.client.get(
            url,
            {"form_id": "stats_form_001"},
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(
            data["total_plots"], 5
        )
        # 10+11+12+13+14 = 60
        self.assertAlmostEqual(
            data["total_area_ha"], 60.0
        )
        # 3 approved / 5 total = 60%
        self.assertAlmostEqual(
            data["approval_percentage"], 60.0
        )
        self.assertEqual(
            data["pending_count"], 2
        )
        # pending: 13 + 14 = 27
        self.assertAlmostEqual(
            data["pending_area_ha"], 27.0
        )

    def test_stats_with_region_filter(self):
        url = "/api/v1/odk/plots/stats/"
        res = self.client.get(
            url,
            {
                "form_id": "stats_form_001",
                "region": "No Match",
            },
            **self.auth,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(
            data["total_plots"], 0
        )
        self.assertEqual(
            data["total_area_ha"], 0
        )
        self.assertEqual(
            data["approval_percentage"], 0
        )

    def test_stats_requires_auth(self):
        url = "/api/v1/odk/plots/stats/"
        res = self.client.get(
            url,
            {"form_id": "stats_form_001"},
        )
        self.assertEqual(res.status_code, 401)
```

---

## Step 5: ESLint curly rule enforcement

**File:** `frontend/eslint.config.mjs`

Added `curly: ["error", "all"]` rule to enforce braces on all `if`/`else` statements. Applied `yarn lint --fix` to auto-fix 86 existing violations across the codebase.

---

## API Response Shape

```json
{
  "total_plots": 5023,
  "total_area_ha": 20420.50,
  "approval_percentage": 80.0,
  "pending_count": 1000,
  "pending_area_ha": 5230.75
}
```

---

## Files Modified/Created

| Action | File |
|--------|------|
| Modify | `backend/api/v1/v1_odk/plot_views.py` |
| Create | `backend/api/v1/v1_odk/tests/tests_stats_endpoint.py` |
| Create | `frontend/src/hooks/useStats.js` |
| Modify | `frontend/src/app/dashboard/page.js` |
| Modify | `frontend/eslint.config.mjs` |
| Modify | 20+ frontend files (curly brace auto-fix) |

## Verification

1. `cd backend && black . && isort . && flake8` - linting
2. `python manage.py test api.v1.v1_odk.tests.tests_stats_endpoint` - 3 tests pass
3. `yarn lint` in frontend container - no errors
4. Hit `GET /api/v1/odk/plots/stats/?form_id=<uid>` in Swagger UI
5. Check dashboard cards show real values and update when filters change
