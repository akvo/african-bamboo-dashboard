"use client";

import { Calendar } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useForms } from "@/hooks/useForms";

export function FilterBar() {
  const { forms, activeForm, setActiveForm } = useForms();

  function handleFormChange(assetUid) {
    const form = forms.find((f) => f.asset_uid === assetUid);
    if (form) {
      setActiveForm(form);
    }
  }

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <Select
        value={activeForm?.asset_uid || ""}
        onValueChange={handleFormChange}
      >
        <SelectTrigger>
          <SelectValue placeholder="Form" />
        </SelectTrigger>
        <SelectContent>
          {forms.map((form) => (
            <SelectItem key={form.asset_uid} value={form.asset_uid}>
              {form.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <div className="flex items-center gap-2">
        <Select defaultValue="7days">
          <SelectTrigger className="w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7days">Last 7 days</SelectItem>
            <SelectItem value="30days">Last 30 days</SelectItem>
            <SelectItem value="90days">Last 90 days</SelectItem>
          </SelectContent>
        </Select>

        <div className="flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm text-muted-foreground">
          <Calendar className="size-4" />
          <span>Jan 24 - Feb 24 2023</span>
        </div>

        <Button variant="outline" size="sm">
          Reset
        </Button>
      </div>
    </div>
  );
}
