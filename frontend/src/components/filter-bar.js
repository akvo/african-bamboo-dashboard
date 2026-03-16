"use client";

import { useMemo, useState } from "react";
import { format } from "date-fns";
import { Calendar as CalendarIcon, FunnelPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
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
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

const DATE_PRESETS = [
  { value: "7days", label: "Last 7 days", days: 7 },
  { value: "30days", label: "Last 30 days", days: 30 },
  { value: "90days", label: "Last 90 days", days: 90 },
];

export function FilterBar({
  region,
  subRegion,
  startDate,
  endDate,
  onRegionChange,
  onSubRegionChange,
  onDateRangeChange,
  onDynamicFilterChange,
  onReset,
  dynamicValues = {},
  regions = [],
  sub_regions = [],
  dynamicFilters = [],
}) {
  const activeChips = useMemo(() => {
    const chips = [];
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
  }, [dynamicValues, dynamicFilters, onDynamicFilterChange]);

  const hasActiveFilters =
    region ||
    subRegion ||
    startDate ||
    endDate ||
    Object.values(dynamicValues).some(Boolean);

  const [dialogOpen, setDialogOpen] = useState(false);

  const activeFilterCount = activeChips.length;

  const dateLabel = useMemo(() => {
    if (!startDate && !endDate) return null;
    const fmt = (d) => format(d, "dd MMM yyyy");
    if (startDate && endDate) return `${fmt(startDate)} - ${fmt(endDate)}`;
    if (startDate) return `From ${fmt(startDate)}`;
    return `Until ${fmt(endDate)}`;
  }, [startDate, endDate]);

  function handlePreset(preset) {
    const match = DATE_PRESETS.find((p) => p.value === preset);
    if (!match) return;
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - match.days);
    onDateRangeChange?.(start, end);
  }

  function handleCalendarSelect(range) {
    onDateRangeChange?.(range?.from || null, range?.to || null);
  }

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
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
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
                <Button
                  variant="outline"
                  onClick={() => {
                    onReset?.();
                    setDialogOpen(false);
                  }}
                >
                  Reset filters
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </div>

      <div className="flex items-center justify-end gap-2">
        <Popover>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              className={cn(
                "w-[260px] justify-start text-left font-normal",
                !startDate && !endDate && "text-muted-foreground",
              )}
            >
              <CalendarIcon className="size-4" />
              {dateLabel || "Pick a date range"}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="end">
            <div className="flex gap-1 border-b px-3 py-2">
              {DATE_PRESETS.map((p) => (
                <Button
                  key={p.value}
                  variant="ghost"
                  size="xs"
                  onClick={() => handlePreset(p.value)}
                >
                  {p.label}
                </Button>
              ))}
            </div>
            <Calendar
              mode="range"
              selected={
                startDate || endDate
                  ? { from: startDate || undefined, to: endDate || undefined }
                  : undefined
              }
              onSelect={handleCalendarSelect}
              numberOfMonths={2}
              defaultMonth={startDate || new Date()}
              disabled={{ after: new Date() }}
            />
          </PopoverContent>
        </Popover>

        {hasActiveFilters && (
          <Button variant="outline" size="sm" onClick={onReset}>
            Reset
          </Button>
        )}
      </div>
    </div>
  );
}
