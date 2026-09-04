class JobTypes:
    export_shapefile = 1
    export_geojson = 2
    export_xlsx = 3

    FieldStr = {
        export_shapefile: "export_shapefile",
        export_geojson: "export_geojson",
        export_xlsx: "export_xlsx",
    }


class JobStatus:
    pending = 1
    on_progress = 2
    failed = 3
    done = 4

    FieldStr = {
        pending: "pending",
        on_progress: "on_progress",
        failed: "failed",
        done: "done",
    }


# Per-task timeout for export jobs. Must stay below
# Q_CLUSTER["retry"] so a running export is never redelivered.
EXPORT_TASK_TIMEOUT = 540

# A job still pending/on_progress this long after creation is
# treated as abandoned — almost always a dead qcluster worker.
JOB_STALE_SECONDS = 600
