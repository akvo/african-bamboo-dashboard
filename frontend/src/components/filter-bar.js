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

export function FilterBar() {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <Select>
        <SelectTrigger className="w-[180px]">
          <SelectValue placeholder="Region" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All Regions</SelectItem>
          <SelectItem value="sidama">Sidama</SelectItem>
          <SelectItem value="oromia">Oromia</SelectItem>
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
