"use client";

import { useMemo } from "react";
import { Calendar, FunnelPlus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const DATE_PRESETS = [
  { value: "7days", label: "Last 7 days" },
  { value: "30days", label: "Last 30 days" },
  { value: "90days", label: "Last 90 days" },
];

export function getDateRange(preset) {
  if (!preset) return { start: null, end: null };
  const now = Date.now();
  const days = { "7days": 7, "30days": 30, "90days": 90 }[preset];
  if (!days) return { start: null, end: null };
  return { start: now - days * 86400000, end: now };
}

function formatDateRange(preset) {
  const { start, end } = getDateRange(preset);
  if (!start || !end) return null;
  const fmt = (ms) =>
    new Date(ms).toLocaleDateString("en-GB", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  return `${fmt(start)} - ${fmt(end)}`;
}

export function FilterBar({
  region,
  subRegion,
  datePreset,
  onRegionChange,
  onSubRegionChange,
  onDatePresetChange,
  onDynamicFilterChange,
  onReset,
  dynamicValues = {},
  regions = [],
  sub_regions = [],
  dynamicFilters = [],
}) {
  const dateLabel = useMemo(() => formatDateRange(datePreset), [datePreset]);

  const activeChips = useMemo(() => {
    const chips = [];
    if (region) {
      const match = regions.find((r) => r.value === region);
      chips.push({
        key: "region",
        label: match?.label || region,
        onClear: () => onRegionChange(""),
      });
    }
    if (subRegion) {
      const match = sub_regions.find((w) => w.value === subRegion);
      chips.push({
        key: "subRegion",
        label: match?.label || subRegion,
        onClear: () => onSubRegionChange(""),
      });
    }
    for (const df of dynamicFilters) {
      const val = dynamicValues[df.name];
      if (val) {
        const match = df.options.find((o) => o.name === val);
        chips.push({
          key: df.name,
          label: `${df.label}: ${match?.label || val}`,
          onClear: () => onDynamicFilterChange?.(df.name, ""),
        });
      }
    }
    return chips;
  }, [
    region,
    subRegion,
    dynamicValues,
    regions,
    sub_regions,
    dynamicFilters,
    onRegionChange,
    onSubRegionChange,
    onDynamicFilterChange,
  ]);

  const hasActiveFilters =
    region ||
    subRegion ||
    datePreset ||
    Object.values(dynamicValues).some(Boolean);

  const activeFilterCount = activeChips.length + (datePreset ? 1 : 0);

  return (
    <div className="w-full flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-center gap-2">
        {regions.length > 0 && (
          <div className="hidden 3xl:block">
            <Select value={region || ""} onValueChange={onRegionChange}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Region" />
              </SelectTrigger>
              <SelectContent>
                {regions.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {sub_regions.length > 0 && (
          <div className="hidden 3xl:block">
            <Select value={subRegion || ""} onValueChange={onSubRegionChange}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Sub-region" />
              </SelectTrigger>
              <SelectContent>
                {sub_regions.map((w) => (
                  <SelectItem key={w.value} value={w.value}>
                    {w.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {(dynamicFilters.length > 0 ||
          regions.length > 0 ||
          sub_regions.length > 0) && (
          <Dialog>
            <DialogTrigger asChild>
              <Button
                variant="outline"
                size="icon"
                className="relative rounded-sm p-3 size-8 flex items-center justify-center"
              >
                <span className="sr-only">Advanced filters</span>
                <FunnelPlus className="size-4" />
                {activeFilterCount > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 flex size-4 items-center justify-center rounded-full bg-primary text-[10px] font-medium text-primary-foreground">
                    {activeFilterCount}
                  </span>
                )}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Advanced Filters</DialogTitle>
                <DialogDescription>
                  Narrow results using additional criteria.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                {regions.length > 0 && (
                  <div className="block 3xl:hidden">
                    <label className="block text-sm font-medium mb-1">
                      Region
                    </label>
                    <Select value={region || ""} onValueChange={onRegionChange}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select region" />
                      </SelectTrigger>
                      <SelectContent>
                        {regions.map((r) => (
                          <SelectItem key={r.value} value={r.value}>
                            {r.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {sub_regions.length > 0 && (
                  <div className="block 3xl:hidden">
                    <label className="block text-sm font-medium mb-1">
                      Sub-region
                    </label>
                    <Select
                      value={subRegion || ""}
                      onValueChange={onSubRegionChange}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select sub-region" />
                      </SelectTrigger>
                      <SelectContent>
                        {sub_regions.map((w) => (
                          <SelectItem key={w.value} value={w.value}>
                            {w.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {dynamicFilters.map((df) => (
                  <div key={df.name}>
                    <label className="block text-sm font-medium mb-1">
                      {df.label}
                    </label>
                    <Select
                      value={dynamicValues[df.name] || ""}
                      onValueChange={(val) =>
                        onDynamicFilterChange?.(df.name, val)
                      }
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder={`Select ${df.label}`} />
                      </SelectTrigger>
                      <SelectContent>
                        {df.options.map((opt) => (
                          <SelectItem key={opt.name} value={opt.name}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ))}
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={onReset}>
                  Reset filters
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      {activeChips.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {activeChips.map((chip) => (
            <span
              key={chip.key}
              data-testid={`filter-chip-${chip.key}`}
              className="inline-flex items-center gap-1 rounded-full border bg-muted px-2.5 py-0.5 text-xs font-medium"
            >
              {chip.label}
              <button
                type="button"
                aria-label={`Remove ${chip.label} filter`}
                className="ml-0.5 rounded-full p-0.5 hover:bg-muted-foreground/20"
                onClick={chip.onClear}
              >
                <X className="size-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center justify-end gap-2">
        <Select value={datePreset || ""} onValueChange={onDatePresetChange}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="Date range" />
          </SelectTrigger>
          <SelectContent>
            {DATE_PRESETS.map((p) => (
              <SelectItem key={p.value} value={p.value}>
                {p.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {dateLabel && (
          <div className="flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm text-muted-foreground">
            <Calendar className="size-4" />
            <span>{dateLabel}</span>
          </div>
        )}

        {hasActiveFilters && (
          <Button variant="outline" size="sm" onClick={onReset}>
            Reset
          </Button>
        )}
      </div>
    </div>
  );
}
