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
    <div className="absolute left-1/2 top-16 z-[1000] flex w-full max-w-md -translate-x-1/2 flex-col overflow-hidden rounded-lg border border-border bg-card shadow-lg">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-orange-400 opacity-75" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-orange-500" />
        </span>
        <span className="text-sm font-semibold">Editing: {plotName}</span>
      </div>
      <div className="mx-3 mb-3 rounded-md bg-muted/60 px-3 py-2">
        <ul className="list-disc flex gap-3 text-xs text-muted-foreground">
          <li className="pr-3">
            <span className="font-medium text-foreground">Drag vertices</span>{" "}
            move
          </li>
          <li className="pr-3">
            <span className="font-medium text-foreground">Drag midpoints</span>{" "}
            add
          </li>
          <li>
            <span className="font-medium text-foreground">Click vertex</span>{" "}
            delete
          </li>
        </ul>
      </div>

      {/* Footer actions */}
      <div className="flex items-center gap-2 border-t border-border bg-muted/30 px-3 py-2.5">
        <Button
          size="sm"
          variant="secondary"
          className="h-8 text-xs"
          onClick={onReset}
          disabled={isResetting}
        >
          {isResetting ? "Resetting..." : "Reset"}
        </Button>
        <div className="flex-1" />
        <Button
          size="sm"
          variant="outline"
          className="h-8 text-xs"
          onClick={onCancel}
        >
          Cancel
        </Button>
        <Button
          size="sm"
          className="h-8 text-xs"
          onClick={onSave}
          disabled={!hasChanges}
        >
          Save
        </Button>
      </div>
    </div>
  );
}
