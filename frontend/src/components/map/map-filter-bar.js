"use client";

import { useRef, useEffect } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { useForms } from "@/hooks/useForms";

function stopLeafletPropagation(el) {
  if (!el) return;
  const stop = (e) => e.stopPropagation();
  el.addEventListener("mousedown", stop);
  el.addEventListener("dblclick", stop);
  el.addEventListener("wheel", stop);
  el.addEventListener("touchstart", stop);
}

export default function MapFilterBar() {
  const { forms, activeForm, setActiveForm } = useForms();
  const ref = useRef(null);

  useEffect(() => {
    stopLeafletPropagation(ref.current);
  }, []);

  return (
    <div
      ref={ref}
      className="pointer-events-auto absolute left-3 right-3 top-3 z-[999] flex items-center gap-2 rounded-lg border border-border bg-card/90 px-3 py-2 shadow-md backdrop-blur-sm"
    >
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

      <Button
        variant="ghost"
        size="sm"
        className="h-8 text-xs"
        onClick={() => {}}
      >
        Reset
      </Button>
    </div>
  );
}
