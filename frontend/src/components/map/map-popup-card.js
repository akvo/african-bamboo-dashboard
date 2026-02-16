"use client";

import { StatusBadge } from "@/components/status-badge";
import { getPlotStatus } from "@/lib/plot-utils";

export default function MapPopupCard({ plot }) {
  const status = getPlotStatus(plot);

  return (
    <div className="min-w-[200px] space-y-1.5">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold">{plot.plot_name}</span>
        <StatusBadge status={status} />
      </div>
      <p className="text-xs text-gray-600">{plot.instance_name}</p>
      <p className="text-xs text-gray-500">
        {plot.region} / {plot.sub_region}
      </p>
    </div>
  );
}
