"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useForms } from "@/hooks/useForms";
import basemaps, { DEFAULT_BASEMAP } from "@/lib/basemap-config";

export default function MapFilterBar({
  basemap = DEFAULT_BASEMAP,
  onBasemapChange,
}) {
  const { forms, activeForm, setActiveForm } = useForms();

  return (
    <div className="absolute left-3 right-3 top-3 z-[999] flex items-center gap-2 rounded-lg border border-border bg-card/90 px-3 py-2 shadow-md backdrop-blur-sm">
      <Select
        value={activeForm?.asset_uid || ""}
        onValueChange={(uid) => {
          const form = forms.find((f) => f.asset_uid === uid);
          if (form) setActiveForm(form);
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

      <div className="flex-1" />

      <Select value={basemap} onValueChange={onBasemapChange}>
        <SelectTrigger size="sm" className="h-8 w-[120px] text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {basemaps.map((b) => (
            <SelectItem key={b.id} value={b.id}>
              {b.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
