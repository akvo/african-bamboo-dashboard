"use client";

import { useMemo } from "react";
import { MoreVertical, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
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
import { useForms } from "@/hooks/useForms";
import { useMapState } from "@/hooks/useMapState";

export default function PlotListPanel({
  plots,
  count,
  activeTab,
  sortBy,
  search,
  selectedPlotId,
  onTabChange,
  onSortChange,
  onSearchChange,
  onSelectPlot,
}) {
  const { forms, activeForm, setActiveForm, setIsChanged } = useForms();
  const { handleResetFilters } = useMapState();
  // Enrich with _status for display; filtering/sorting now server-side
  const enrichedPlots = useMemo(() => {
    let items = plots.map((p) => ({
      ...p,
      _status: getPlotStatus(p),
    }));

    // Client-side priority sort (not supported server-side)
    if (sortBy === "priority") {
      const order = { flagged: 0, pending: 1, rejected: 2, approved: 3 };
      items.sort((a, b) => (order[a._status] ?? 2) - (order[b._status] ?? 2));
    }

    return items;
  }, [plots, sortBy]);

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
      <div className="w-full flex items-center gap-2 justify-between border-b border-border px-4 py-2">
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
        <Select
          value={activeForm?.asset_uid || ""}
          onValueChange={async (uid) => {
            const form = forms.find((f) => f.asset_uid === uid);
            if (form) {
              setActiveForm(form);
              setIsChanged(true);
              handleResetFilters();
            }
          }}
        >
          <SelectTrigger size="sm" className="h-8 max-w-[200px] text-xs">
            <SelectValue placeholder="Select form" />
          </SelectTrigger>
          <SelectContent>
            {forms.map((f) => (
              <SelectItem key={f.asset_uid} value={f.asset_uid}>
                {f.name || f.asset_uid}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="w-full px-4 py-2">
        <div className="relative w-full">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search"
            value={search || ""}
            onChange={(e) => onSearchChange?.(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>
      {/* Status Tabs */}
      <div className="w-full pb-2">
        <Tabs value={activeTab} onValueChange={onTabChange}>
          <TabsList className="mx-4 mt-2 w-auto">
            <TabsTrigger value="all">View all</TabsTrigger>
            <TabsTrigger value="approved">Approved</TabsTrigger>
            <TabsTrigger value="pending">On Hold</TabsTrigger>
            <TabsTrigger value="rejected">Rejected</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Plot list */}
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-2 p-2">
          {enrichedPlots.length === 0 && (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">
              No plots found
            </p>
          )}
          {enrichedPlots.map((plot) => (
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
