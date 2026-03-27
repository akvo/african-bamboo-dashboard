"use client";

import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function EditableField({
  questionName,
  label,
  rawValue,
  type,
  options,
  onChange,
}) {
  if (type === "select_one" && options?.length) {
    return (
      <div className="flex flex-1 flex-col gap-1">
        <span className="text-sm text-muted-foreground">{label}</span>
        <Select
          value={rawValue ?? ""}
          onValueChange={(v) => onChange(questionName, v)}
        >
          <SelectTrigger className="h-8 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {options.map((opt) => (
              <SelectItem key={opt.name} value={opt.name}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      <Input
        className="h-8 text-sm"
        value={rawValue ?? ""}
        onChange={(e) => onChange(questionName, e.target.value)}
      />
    </div>
  );
}
