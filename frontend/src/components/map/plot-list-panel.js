"use client";

import { useMemo } from "react";
import { MoreVertical } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import PlotCardItem from "@/components/map/plot-card-item";
import { getPlotStatus } from "@/lib/plot-utils";

export default function PlotListPanel({
  plots,
  count,
  activeTab,
  sortBy,
  selectedPlotId,
  onTabChange,
  onSortChange,
  onSelectPlot,
}) {
  const filteredPlots = useMemo(() => {
    let filtered = plots.map((p) => ({
      ...p,
      _status: getPlotStatus(p),
    }));

    if (activeTab !== "all") {
      filtered = filtered.filter((p) => p._status === activeTab);
    }

    filtered.sort((a, b) => {
      if (sortBy === "name") return a.plot_name.localeCompare(b.plot_name);
      if (sortBy === "date") return b.created_at - a.created_at;
      // priority: pending first, then rejected, then approved
      const order = { pending: 0, rejected: 1, approved: 2 };
      return (order[a._status] ?? 1) - (order[b._status] ?? 1);
    });

    return filtered;
  }, [plots, activeTab, sortBy]);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">{count} plots detected</h2>
        <Button variant="ghost" size="icon-sm">
          <MoreVertical className="size-4" />
        </Button>
      </div>

      {/* Sort */}
      <div className="border-b border-border px-4 py-2">
        <Select value={sortBy} onValueChange={onSortChange}>
          <SelectTrigger size="sm" className="h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="priority">Sort: Priority</SelectItem>
            <SelectItem value="name">Sort: Name</SelectItem>
            <SelectItem value="date">Sort: Date</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Status Tabs */}
      <Tabs value={activeTab} onValueChange={onTabChange}>
        <TabsList className="mx-4 mt-2 w-auto">
          <TabsTrigger value="all">View all</TabsTrigger>
          <TabsTrigger value="approved">Approved</TabsTrigger>
          <TabsTrigger value="pending">Pending</TabsTrigger>
          <TabsTrigger value="rejected">Rejected</TabsTrigger>
        </TabsList>
      </Tabs>

      {/* Plot list */}
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-1 p-2">
          {filteredPlots.length === 0 && (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">
              No plots found
            </p>
          )}
          {filteredPlots.map((plot) => (
            <PlotCardItem
              key={plot.uuid}
              plot={plot}
              isSelected={plot.uuid === selectedPlotId}
              onClick={() => onSelectPlot(plot.uuid)}
            />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
