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
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { SearchableSelect } from "@/components/searchable-select";
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
  onActiveFilterFieldsChange,
  onReset,
  dynamicValues = {},
  regions = [],
  sub_regions = [],
  dynamicFilters = [],
  availableFilters = [],
  activeFilterFields = [],
}) {
  // Derive visible dynamic filters from availableFilters + activeFilterFields
  // so toggling in "Manage Filters" is reflected instantly without a refresh.
  // Falls back to dynamicFilters prop when availableFilters is empty.
  const visibleDynamicFilters = useMemo(() => {
    if (availableFilters.length > 0) {
      return availableFilters.filter((af) =>
        activeFilterFields.includes(af.name),
      );
    }
    return dynamicFilters;
  }, [availableFilters, activeFilterFields, dynamicFilters]);

  const activeChips = useMemo(() => {
    const chips = [];
    for (const df of visibleDynamicFilters) {
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
  }, [dynamicValues, visibleDynamicFilters, onDynamicFilterChange]);

  const hasActiveFilters =
    region ||
    subRegion ||
    startDate ||
    endDate ||
    Object.values(dynamicValues).some(Boolean);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [presetValue, setPresetValue] = useState("");

  const activeFilterCount = activeChips.length;

  const dateLabel = useMemo(() => {
    if (!startDate && !endDate) return null;
    const fmt = (d) => format(d, "dd MMM yyyy");
    if (startDate && endDate) return `${fmt(startDate)} - ${fmt(endDate)}`;
    if (startDate) return `From ${fmt(startDate)}`;
    return `Until ${fmt(endDate)}`;
  }, [startDate, endDate]);

  const activePreset =
    presetValue && startDate && endDate
      ? presetValue
      : startDate || endDate
        ? "custom"
        : "";

  function handlePreset(preset) {
    const match = DATE_PRESETS.find((p) => p.value === preset);
    if (!match) return;
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - match.days);
    setPresetValue(preset);
    onDateRangeChange?.(start, end);
  }

  function handleCalendarSelect(range) {
    setPresetValue("");
    onDateRangeChange?.(range?.from || null, range?.to || null);
  }

  const sortedRegions = useMemo(
    () =>
      [...regions].sort((a, b) =>
        a.label.localeCompare(b.label, undefined, { sensitivity: "base" }),
      ),
    [regions],
  );

  const sortedSubRegions = useMemo(
    () =>
      [...sub_regions].sort((a, b) =>
        a.label.localeCompare(b.label, undefined, { sensitivity: "base" }),
      ),
    [sub_regions],
  );

  const hasAdvancedFilters =
    visibleDynamicFilters.length > 0 ||
    regions.length > 0 ||
    sub_regions.length > 0 ||
    availableFilters.length > 0;

  return (
    <div className="w-full flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-center gap-2">
        {regions.length > 0 && (
          <div className="hidden 3xl:block">
            <SearchableSelect
              options={sortedRegions.map((r) => ({
                value: r.value,
                label: r.label,
              }))}
              value={region || ""}
              onValueChange={onRegionChange}
              placeholder="Region"
              className="w-[160px]"
            />
          </div>
        )}

        {sub_regions.length > 0 && (
          <div className="hidden 3xl:block">
            <SearchableSelect
              options={sortedSubRegions.map((w) => ({
                value: w.value,
                label: w.label,
              }))}
              value={subRegion || ""}
              onValueChange={onSubRegionChange}
              placeholder="Sub-region"
              className="w-[160px]"
            />
          </div>
        )}

        {hasAdvancedFilters && (
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
                    <SearchableSelect
                      options={sortedRegions.map((r) => ({
                        value: r.value,
                        label: r.label,
                      }))}
                      value={region || ""}
                      onValueChange={onRegionChange}
                      placeholder="Select region"
                      className="w-full"
                    />
                  </div>
                )}

                {sub_regions.length > 0 && (
                  <div className="block 3xl:hidden">
                    <label className="block text-sm font-medium mb-1">
                      Sub-region
                    </label>
                    <SearchableSelect
                      options={sortedSubRegions.map((w) => ({
                        value: w.value,
                        label: w.label,
                      }))}
                      value={subRegion || ""}
                      onValueChange={onSubRegionChange}
                      placeholder="Select sub-region"
                      className="w-full"
                    />
                  </div>
                )}

                {visibleDynamicFilters.map((df) => (
                  <div key={df.name}>
                    <label className="block text-sm font-medium mb-1">
                      {df.label}
                    </label>
                    <SearchableSelect
                      options={df.options.map((opt) => ({
                        value: opt.name,
                        label: opt.label,
                      }))}
                      value={dynamicValues[df.name] || ""}
                      onValueChange={(val) =>
                        onDynamicFilterChange?.(df.name, val)
                      }
                      placeholder={`Select ${df.label}`}
                      className="w-full"
                    />
                  </div>
                ))}

                {/* Manage Filters Section */}
                {availableFilters.length > 0 && (
                  <div className="border-t pt-4">
                    <h4 className="text-sm font-medium mb-3">Manage Filters</h4>
                    <div className="space-y-3">
                      {availableFilters.map((af) => (
                        <div
                          key={af.name}
                          className="flex items-center justify-between"
                        >
                          <Label
                            htmlFor={`toggle-${af.name}`}
                            className="text-sm"
                          >
                            {af.label}
                          </Label>
                          <Switch
                            id={`toggle-${af.name}`}
                            checked={activeFilterFields.includes(af.name)}
                            onCheckedChange={(checked) => {
                              const next = checked
                                ? [...activeFilterFields, af.name]
                                : activeFilterFields.filter(
                                    (n) => n !== af.name,
                                  );
                              onActiveFilterFieldsChange?.(next);
                            }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
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
        <Select
          value={activePreset}
          onValueChange={(val) => {
            if (val === "custom") {
              setCalendarOpen(true);
              return;
            }
            handlePreset(val);
          }}
        >
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="Date range" />
          </SelectTrigger>
          <SelectContent>
            {DATE_PRESETS.map((p) => (
              <SelectItem key={p.value} value={p.value}>
                {p.label}
              </SelectItem>
            ))}
            <SelectItem value="custom">Custom range</SelectItem>
          </SelectContent>
        </Select>

        <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              className={cn(
                "justify-start text-left font-normal",
                !startDate && !endDate && "text-muted-foreground",
              )}
            >
              <CalendarIcon className="size-4" />
              {dateLabel || "Pick dates"}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="end">
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
