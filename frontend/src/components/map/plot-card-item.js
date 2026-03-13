"use client";

import { ArrowRight, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";
import { getPlotStatus } from "@/lib/plot-utils";
import { Separator } from "@/components/ui/separator";

const PlotCardItem = ({
  plot,
  isSelected,
  onClick,
  lastCheckedBy,
  lastCheckedAt,
}) => {
  if (!plot) {
    return null;
  }

  const status = getPlotStatus(plot);

  const alertMessage = plot.flagged_for_review
    ? plot.flagged_reason?.includes("Polygon overlaps with")
      ? "Plot overlap detected"
      : "Several data issues detected"
    : null;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full min-w-0 cursor-pointer flex-col overflow-hidden rounded-md text-left transition-colors",
        "border border-card-foreground/10 bg-card hover:bg-accent",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isSelected && "bg-accent",
      )}
      data-status={status}
    >
      {/* Header: Plot ID + Status badge */}
      <div className="flex w-full items-center justify-between px-3 py-2.5">
        <div className="flex flex-col min-w-0 gap-1">
          <span className="truncate text-sm font-bold text-foreground">
            {plot.plot_name || plot.instance_name}
          </span>
          {plot.plot_name && (
            <span className="truncate text-sm text-muted-foreground">
              {plot.instance_name}
            </span>
          )}
        </div>
        <StatusBadge status={status} />
      </div>

      <Separator className="bg-muted-foreground/20" />

      {/* Enumerator / Region */}
      <div className="flex w-full divide-x divide-muted-foreground/20 px-3 py-2.5">
        <div className="min-w-0 flex-1 pr-3">
          <p className="text-xs text-muted-foreground">Enumerator:</p>
          <p className="truncate text-sm text-foreground">
            {plot.enumerator || "—"}
          </p>
        </div>
        <div className="min-w-0 flex-1 pl-3">
          <p className="text-xs text-muted-foreground">Region:</p>
          <p className="truncate text-sm text-foreground">
            {plot.region || "—"}
          </p>
        </div>
      </div>

      <Separator className="bg-muted-foreground/20" />

      {/* Last checked by */}
      <div className="flex w-full items-center gap-2 px-3 py-2.5">
        <div className="min-w-0 flex-1">
          <p className="text-xs text-muted-foreground">Last checked by:</p>
          <div className="flex items-center gap-2">
            <span className="truncate text-sm text-foreground">
              {lastCheckedBy || "—"}
            </span>
            {lastCheckedAt && (
              <>
                <span className="size-1 shrink-0 rounded-full bg-muted-foreground" />
                <span className="whitespace-nowrap text-xs text-muted-foreground">
                  {new Date(lastCheckedAt).toLocaleDateString("en-GB")}
                </span>
              </>
            )}
          </div>
        </div>
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
          <ArrowRight className="size-4 text-muted-foreground" />
        </div>
      </div>

      {/* Alert banner */}
      {alertMessage && (
        <div className="w-full px-3 pb-3">
          <div className="flex items-center justify-center gap-1.5 rounded-md border border-status-flagged/30 bg-status-flagged/10 px-2 py-1.5">
            <AlertTriangle className="size-3 shrink-0 text-status-flagged" />
            <p className="text-xs font-medium text-status-flagged">
              {alertMessage}
            </p>
          </div>
        </div>
      )}
    </button>
  );
};

export default PlotCardItem;
