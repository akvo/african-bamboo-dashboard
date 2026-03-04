import json
import os
import tempfile
import zipfile
from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from api.v1.v1_jobs.constants import (
    JobStatus,
    JobTypes,
)
from api.v1.v1_jobs.models import Jobs
from api.v1.v1_odk.export import (
    generate_shapefile,
)
from utils.storage import get_path
from api.v1.v1_odk.models import (
    FormMetadata,
    Plot,
    Submission,
)
from api.v1.v1_odk.tests.mixins import (
    OdkTestHelperMixin,
)

VALID_WKT = (
    "POLYGON(("
    "38.47 7.05,"
    "38.48 7.05,"
    "38.48 7.06,"
    "38.47 7.06,"
    "38.47 7.05))"
)

EXPORT_URL = "/api/v1/odk/plots/export/"
JOB_URL = "/api/v1/jobs/{job_id}/"
DOWNLOAD_URL = (
    "/api/v1/jobs/{job_id}/download/"
)


@override_settings(
    USE_TZ=False, TEST_ENV=True
)
class PlotExportEndpointTest(
    TestCase, OdkTestHelperMixin
):
    def setUp(self):
        self.user = self.create_kobo_user()
        self.auth = self.get_auth_header()
        self.form = FormMetadata.objects.create(
            asset_uid="export-form-1",
            name="Export Test Form",
            polygon_field="geoshape",
            region_field="region",
            sub_region_field="woreda",
            plot_name_field="farmer_name",
        )

    def _create_plot(
        self,
        name="Farmer A",
        wkt=VALID_WKT,
        approval_status=None,
        flagged=None,
        flagged_reason=None,
    ):
        sub = Submission.objects.create(
            uuid=f"sub-{name}-{Plot.objects.count()}",
            form=self.form,
            kobo_id=str(
                100 + Plot.objects.count()
            ),
            submission_time=1700000000000,
            raw_data={
                "geoshape": (
                    "7.05 38.47 0 0;"
                    "7.06 38.47 0 0;"
                    "7.06 38.48 0 0;"
                    "7.05 38.48 0 0;"
                    "7.05 38.47 0 0"
                ),
                "farmer_name": name,
                "region": "Amhara",
                "woreda": "Bahir Dar",
                "enumerator_id": "enum_01",
            },
            approval_status=approval_status,
        )
        return Plot.objects.create(
            submission=sub,
            form=self.form,
            plot_name=name,
            polygon_wkt=wkt,
            min_lat=7.05,
            max_lat=7.06,
            min_lon=38.47,
            max_lon=38.48,
            region="Amhara",
            sub_region="Bahir Dar",
            created_at=1700000000000,
            flagged_for_review=flagged,
            flagged_reason=flagged_reason,
        )

    # --- Auth & Validation Tests ---

    def test_export_requires_auth(self):
        resp = self.client.post(
            EXPORT_URL,
            {"form_id": "export-form-1"},
            content_type="application/json",
        )
        self.assertEqual(
            resp.status_code, 401
        )

    @patch(
        "api.v1.v1_odk.views.async_task",
        return_value="fake-task-id",
    )
    def test_export_requires_form_id(
        self, _mock_task
    ):
        resp = self.client.post(
            EXPORT_URL,
            {},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(
            resp.status_code, 400
        )

    @patch(
        "api.v1.v1_odk.views.async_task",
        return_value="fake-task-id",
    )
    def test_export_invalid_form_id(
        self, _mock_task
    ):
        resp = self.client.post(
            EXPORT_URL,
            {"form_id": "nonexistent"},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(
            resp.status_code, 404
        )

    @patch(
        "api.v1.v1_odk.views.async_task",
        return_value="fake-task-id",
    )
    def test_export_invalid_format(
        self, _mock_task
    ):
        resp = self.client.post(
            EXPORT_URL,
            {
                "form_id": "export-form-1",
                "format": "csv",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(
            resp.status_code, 400
        )

    # --- Job Creation Tests ---

    @patch(
        "api.v1.v1_odk.views.async_task",
        return_value="fake-task-id",
    )
    def test_export_creates_job(
        self, mock_task
    ):
        self._create_plot()
        resp = self.client.post(
            EXPORT_URL,
            {"form_id": "export-form-1"},
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(
            resp.status_code, 201
        )
        data = resp.json()
        self.assertIn("id", data)
        self.assertEqual(
            data["status"], "pending"
        )
        self.assertEqual(
            data["type"], "export_shapefile"
        )

        job = Jobs.objects.get(pk=data["id"])
        self.assertEqual(
            job.task_id, "fake-task-id"
        )
        self.assertEqual(
            job.info["form_id"],
            "export-form-1",
        )
        mock_task.assert_called_once()

    @patch(
        "api.v1.v1_odk.views.async_task",
        return_value="fake-task-id",
    )
    def test_export_geojson_format(
        self, mock_task
    ):
        self._create_plot()
        resp = self.client.post(
            EXPORT_URL,
            {
                "form_id": "export-form-1",
                "format": "geojson",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(
            resp.status_code, 201
        )
        data = resp.json()
        self.assertEqual(
            data["type"], "export_geojson"
        )

    @patch(
        "api.v1.v1_odk.views.async_task",
        return_value="fake-task-id",
    )
    def test_export_stores_filters(
        self, _mock_task
    ):
        resp = self.client.post(
            EXPORT_URL,
            {
                "form_id": "export-form-1",
                "status": "approved",
                "search": "Farmer",
            },
            content_type="application/json",
            **self.auth,
        )
        self.assertEqual(
            resp.status_code, 201
        )
        job = Jobs.objects.get(
            pk=resp.json()["id"]
        )
        filters = job.info["filters"]
        self.assertEqual(
            filters["status"], "approved"
        )
        self.assertEqual(
            filters["search"], "Farmer"
        )

    # --- Job Status Tests ---

    def test_job_status_endpoint(self):
        job = Jobs.objects.create(
            type=JobTypes.export_shapefile,
            status=JobStatus.on_progress,
            created_by=self.user,
            info={
                "form_id": "export-form-1"
            },
        )
        resp = self.client.get(
            JOB_URL.format(job_id=job.id),
            **self.auth,
        )
        self.assertEqual(
            resp.status_code, 200
        )
        data = resp.json()
        self.assertEqual(
            data["status"], "on_progress"
        )

    # --- Download Tests ---

    def test_download_not_completed(self):
        job = Jobs.objects.create(
            type=JobTypes.export_shapefile,
            status=JobStatus.on_progress,
            created_by=self.user,
        )
        resp = self.client.get(
            DOWNLOAD_URL.format(
                job_id=job.id
            ),
            **self.auth,
        )
        self.assertEqual(
            resp.status_code, 400
        )

    def test_download_file_not_found(self):
        job = Jobs.objects.create(
            type=JobTypes.export_shapefile,
            status=JobStatus.done,
            created_by=self.user,
            info={
                "file_path": "/nonexistent.zip"
            },
        )
        resp = self.client.get(
            DOWNLOAD_URL.format(
                job_id=job.id
            ),
            **self.auth,
        )
        self.assertEqual(
            resp.status_code, 404
        )

    # --- Shapefile Generation Tests ---

    def test_generate_shapefile_output(self):
        """Test that generate_shapefile
        produces a valid zip with all
        required files."""
        self._create_plot(name="Farmer A")
        self._create_plot(name="Farmer B")

        qs = Plot.objects.filter(
            form=self.form
        )
        rel_path, count = generate_shapefile(
            qs, self.form, "test"
        )
        full = get_path(rel_path)

        self.assertEqual(count, 2)
        self.assertTrue(os.path.exists(full))

        with zipfile.ZipFile(
            full, "r"
        ) as zf:
            names = zf.namelist()
            self.assertIn("test.shp", names)
            self.assertIn("test.shx", names)
            self.assertIn("test.dbf", names)
            self.assertIn("test.prj", names)

            prj = zf.read("test.prj").decode()
            self.assertIn(
                "GCS_WGS_1984", prj
            )

        os.remove(full)

    def test_shapefile_skips_null_geometry(
        self,
    ):
        """Plots without geometry should be
        skipped."""
        self._create_plot(name="With Geo")
        self._create_plot(
            name="No Geo", wkt=None
        )

        qs = Plot.objects.filter(
            form=self.form,
            polygon_wkt__isnull=False,
        ).exclude(polygon_wkt="")

        rel_path, count = generate_shapefile(
            qs, self.form, "test2"
        )
        self.assertEqual(count, 1)

        full = get_path(rel_path)
        if os.path.exists(full):
            os.remove(full)

    def test_shapefile_uses_edited_geometry(
        self,
    ):
        """Export should use polygon_wkt
        (edited in DCU), not raw Kobo data."""
        edited_wkt = (
            "POLYGON(("
            "38.50 7.10,"
            "38.51 7.10,"
            "38.51 7.11,"
            "38.50 7.11,"
            "38.50 7.10))"
        )
        self._create_plot(
            name="Edited",
            wkt=edited_wkt,
        )

        qs = Plot.objects.filter(
            form=self.form
        )
        rel_path, count = generate_shapefile(
            qs, self.form, "test_edited"
        )
        full = get_path(rel_path)
        self.assertEqual(count, 1)

        import shapefile as shp

        with tempfile.TemporaryDirectory() \
                as tmpdir:
            with zipfile.ZipFile(
                full, "r"
            ) as zf:
                zf.extractall(tmpdir)

            sf = shp.Reader(
                os.path.join(
                    tmpdir, "test_edited"
                )
            )
            shape = sf.shape(0)
            coords = shape.points
            # Verify exported coords match
            # edited WKT, not raw Kobo
            lons = [c[0] for c in coords]
            self.assertTrue(
                any(
                    38.50 <= lon <= 38.51
                    for lon in lons
                )
            )

        os.remove(full)

    # --- GeoJSON Generation Tests ---

    def test_generate_geojson_output(self):
        """Test that generate_geojson produces
        a valid GeoJSON FeatureCollection."""
        from api.v1.v1_odk.export import (
            generate_geojson,
        )

        self._create_plot(name="GJ Farmer")

        qs = Plot.objects.filter(
            form=self.form
        )
        rel_path, count = generate_geojson(
            qs, self.form, "test_gj"
        )
        full = get_path(rel_path)
        self.assertEqual(count, 1)
        self.assertTrue(
            os.path.exists(full)
        )

        with open(full) as f:
            data = json.load(f)

        self.assertEqual(
            data["type"], "FeatureCollection"
        )
        self.assertEqual(
            len(data["features"]), 1
        )
        feature = data["features"][0]
        self.assertEqual(
            feature["type"], "Feature"
        )
        self.assertIn(
            "Polygon",
            feature["geometry"]["type"],
        )
        props = feature["properties"]
        self.assertEqual(
            props["PLOT_NAME"], "GJ Farmer"
        )
        self.assertEqual(
            props["VAL_STATUS"], "pending"
        )

        os.remove(full)

    # --- Attribute Tests ---

    def test_export_attributes_approved(self):
        """Approved plot should have
        VAL_STATUS='approved'."""
        from api.v1.v1_odk.export import (
            generate_geojson,
        )

        self._create_plot(
            name="Approved Farmer",
            approval_status=1,
        )

        qs = Plot.objects.filter(
            form=self.form
        )
        rel_path, _ = generate_geojson(
            qs, self.form, "test_approved"
        )
        full = get_path(rel_path)

        with open(full) as f:
            data = json.load(f)
        props = data["features"][0][
            "properties"
        ]
        self.assertEqual(
            props["VAL_STATUS"], "approved"
        )

        os.remove(full)

    def test_export_attributes_flagged(self):
        """Flagged plot should have
        NEEDS_RECL='Yes' and REJ_REASON."""
        from api.v1.v1_odk.export import (
            generate_geojson,
        )

        self._create_plot(
            name="Flagged Farmer",
            flagged=True,
            flagged_reason="Overlap detected",
        )

        qs = Plot.objects.filter(
            form=self.form
        )
        rel_path, _ = generate_geojson(
            qs, self.form, "test_flagged"
        )
        full = get_path(rel_path)

        with open(full) as f:
            data = json.load(f)
        props = data["features"][0][
            "properties"
        ]
        self.assertEqual(
            props["NEEDS_RECL"], "Yes"
        )
        self.assertEqual(
            props["REJ_REASON"],
            "Overlap detected",
        )

        os.remove(full)
