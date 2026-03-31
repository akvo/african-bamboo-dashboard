"use client";

import { StatusBadge } from "@/components/status-badge";
import { getPlotStatus } from "@/lib/plot-utils";
import { PREFIX_SUBM_ID } from "@/lib/constants";

export default function MapPopupCard({ plot }) {
  const status = getPlotStatus(plot);

  return (
    <div className="min-w-[200px] space-y-1.5">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold">
          {plot.plot_id ? `${PREFIX_SUBM_ID}${plot.plot_id}` : "—"}
        </span>
        <StatusBadge status={status} />
      </div>
      {plot.main_plot_uid && (
        <p className="text-xs font-semibold text-primary">
          Plot ID: {plot.main_plot_uid}
        </p>
      )}
      <p className="text-xs text-gray-600">{plot.instance_name}</p>
      <p className="text-xs text-gray-500">
        {plot.region} / {plot.sub_region}
      </p>
    </div>
  );
}
