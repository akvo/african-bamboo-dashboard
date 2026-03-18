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
