"use client";

import { useMemo } from "react";
import { Calendar } from "lucide-react";
import { Button } from "@/components/ui/button";
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
    new Date(ms).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  return `${fmt(start)} - ${fmt(end)}`;
}

export function FilterBar({
  regions = [],
  sub_regions = [],
  dynamicFilters = [],
  region,
  subRegion,
  datePreset,
  dynamicValues = {},
  onRegionChange,
  onSubRegionChange,
  onDatePresetChange,
  onDynamicFilterChange,
  onReset,
}) {
  const dateLabel = useMemo(() => formatDateRange(datePreset), [datePreset]);

  const hasActiveFilters =
    region ||
    subRegion ||
    datePreset ||
    Object.values(dynamicValues).some(Boolean);

  return (
    <div className="w-full flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="w-full flex flex-wrap items-center gap-2">
        {regions.length > 0 && (
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
        )}

        {sub_regions.length > 0 && (
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
        )}

        {dynamicFilters.map((df) => (
          <Select
            key={df.name}
            value={dynamicValues[df.name] || ""}
            onValueChange={(val) => onDynamicFilterChange?.(df.name, val)}
          >
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder={df.label} />
            </SelectTrigger>
            <SelectContent>
              {df.options.map((opt) => (
                <SelectItem key={opt.name} value={opt.name}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ))}
      </div>

      <div className="w-fit flex items-center gap-2">
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
