"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { ChevronDown } from "lucide-react";

export function MultiSelectDropdown({
  label,
  placeholder,
  hint,
  items,
  selected,
  onToggle,
  getItemKey = (item) => item.full_path ?? item.name,
  getItemLabel = (item) => `${item.label} (${item.type})`,
  getBadgeLabel,
  scrollable = false,
}) {
  const resolveBadgeLabel =
    getBadgeLabel ||
    ((key) => {
      const item = items.find(
        (i) => i.full_path === key || i.name === key,
      );
      return item?.label || key;
    });

  return (
    <div className="space-y-2">
      {label && <Label>{label}</Label>}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            className="w-full justify-between h-auto min-h-[2.25rem] px-3 py-2"
          >
            <div className="flex flex-wrap gap-1">
              {selected.length === 0 ? (
                <span className="text-muted-foreground">
                  {placeholder || `Select ${label?.toLowerCase()}...`}
                </span>
              ) : (
                selected.map((key) => (
                  <Badge key={key} variant="secondary">
                    {resolveBadgeLabel(key)}
                  </Badge>
                ))
              )}
            </div>
            <ChevronDown className="size-4 opacity-50 shrink-0" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          className={`w-[--radix-dropdown-menu-trigger-width]${
            scrollable ? " max-h-64 overflow-y-auto" : ""
          }`}
        >
          {items.map((item) => {
            const key = getItemKey(item);
            return (
              <DropdownMenuCheckboxItem
                key={key}
                checked={selected.includes(key)}
                onCheckedChange={() => onToggle(key)}
              >
                {getItemLabel(item)}
              </DropdownMenuCheckboxItem>
            );
          })}
        </DropdownMenuContent>
      </DropdownMenu>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
