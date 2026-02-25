"use client";

import { ChevronRight, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";
import { getPlotStatus } from "@/lib/plot-utils";

export default function PlotCardItem({ plot, isSelected, onClick }) {
  const status = getPlotStatus(plot);

  return (
    <div
      role="button"
      onClick={onClick}
      className={cn(
        "flex w-full min-w-0 cursor-pointer flex-col overflow-hidden rounded-md text-left transition-colors duration-200 hover:bg-accent",
        "border border-card-foreground/10 data-[status=flagged]:border-status-flagged/30 data-[status=flagged]:bg-status-flagged/10",
        isSelected && "bg-accent",
      )}
      data-status={status}
    >
      {/* Header: name + badge + chevron */}
      <div className="flex w-full items-center gap-3 border-b border-card-foreground/10 px-3 py-2.5 data-[status=flagged]:border-status-flagged/20">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-foreground">
            {plot.plot_name}
          </p>
          <p className="truncate text-xs text-muted-foreground">
            {plot.instance_name}
          </p>
        </div>
        <StatusBadge status={status} />
        <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
      </div>

      {/* Body: Region / Sub-region */}
      {(plot.region || plot.sub_region) && (
        <div className="grid w-full grid-cols-2 gap-2 border-b border-card-foreground/10 px-3 py-2 data-[status=flagged]:border-status-flagged/20">
          {plot.region && (
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground">Enumerator</p>
              <p className="truncate text-xs font-medium">{plot.enumerator}</p>
            </div>
          )}
          {plot.sub_region && (
            <div className="min-w-0">
              <p className="text-[10px] text-muted-foreground">Region</p>
              <p className="truncate text-xs font-medium">{plot.region}</p>
            </div>
          )}
        </div>
      )}

      {/* Footer: Flagged reason banner */}
      {plot.flagged_for_review && plot.flagged_reason && (
        <div className="flex w-full items-center justify-center px-3 py-2">
          <div className="flex items-center gap-1.5 rounded border border-status-flagged/30 bg-status-flagged/10 px-2 py-1.5">
            <AlertTriangle className="mt-0.5 size-3 shrink-0 text-status-flagged" />
            <p className="text-xs text-status-flagged">
              Several data issues detected
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
