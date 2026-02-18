"use client";

import { Button } from "@/components/ui/button";

export default function MapEditToolbar({
  plotName,
  onSave,
  onCancel,
  onReset,
  isResetting,
  hasChanges,
}) {
  return (
    <div className="absolute left-1/2 top-16 z-[1000] flex -translate-x-1/2 flex-col items-center gap-1 rounded-lg border border-border bg-card px-4 py-2 shadow-lg">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-orange-500" />
          <span className="text-sm font-medium">Editing: {plotName}</span>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="secondary"
            onClick={onReset}
            disabled={isResetting}
          >
            {isResetting ? "Resetting..." : "Reset"}
          </Button>
          <Button size="sm" onClick={onSave} disabled={!hasChanges}>
            Save
          </Button>
          <Button size="sm" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Drag vertices to move · Drag midpoints to add · Right-click vertex to
        delete
      </p>
    </div>
  );
}
