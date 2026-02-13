"use client";

import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";
import { getPlotStatus } from "@/lib/plot-utils";

export default function PlotCardItem({ plot, isSelected, onClick }) {
  const status = getPlotStatus(plot);

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full cursor-pointer items-center gap-3 rounded-md px-3 py-2.5 text-left transition-colors duration-200 hover:bg-accent",
        isSelected && "bg-accent",
      )}
    >
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
    </button>
  );
}
