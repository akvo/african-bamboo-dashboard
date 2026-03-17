"use client";

import { useState } from "react";
import {
  AlertTriangle,
  AlertCircle,
  Paperclip,
  EllipsisVertical,
  ChevronLeft,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatusBadge } from "@/components/status-badge";
import { cn } from "@/lib/utils";
import { FlagMessages, splitFlags } from "@/lib/flag";

function groupFlagsByType(flags) {
  const groups = {};
  for (const flag of flags) {
    const key = flag.type;
    if (!groups[key]) {
      groups[key] = { type: key, severity: flag.severity, items: [] };
    }
    groups[key].items.push(flag);
  }
  return Object.values(groups);
}

function FlagList({ flags }) {
  const [selectedGroup, setSelectedGroup] = useState(null);

  if (!flags || flags.length === 0) {
    return null;
  }

  const groups = groupFlagsByType(flags);

  return (
    <>
      <div className="flex flex-col gap-1.5">
        {groups.map((group) => {
          const isError = group.severity === "error";
          const Icon = isError ? AlertCircle : AlertTriangle;
          const colorClass = isError
            ? "text-status-rejected"
            : "text-status-flagged";
          const borderClass = isError
            ? "border-status-rejected/30 bg-status-rejected/10"
            : "border-status-flagged/30 bg-status-flagged/10";
          const label =
            FlagMessages[group.type] || group.items[0]?.note || group.type;
          const hasDetails = group.items.some((f) => f.note);
          const count = group.items.length;

          return (
            <button
              key={group.type}
              type="button"
              disabled={!hasDetails}
              onClick={() => hasDetails && setSelectedGroup(group)}
              className={cn(
                "flex items-start gap-1.5 rounded-md border px-2 py-1.5 text-left",
                borderClass,
                hasDetails && "cursor-pointer hover:opacity-80",
                !hasDetails && "cursor-default",
              )}
            >
              <Icon className={cn("mt-0.5 size-3 shrink-0", colorClass)} />
              <span className={cn("text-xs font-medium", colorClass)}>
                {label}
                {count > 1 && ` (${count})`}
              </span>
            </button>
          );
        })}
      </div>

      <Dialog
        open={!!selectedGroup}
        onOpenChange={(open) => !open && setSelectedGroup(null)}
      >
        {selectedGroup && (
          <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-sm">
                {selectedGroup.severity === "error" ? (
                  <AlertCircle className="size-4 text-status-rejected" />
                ) : (
                  <AlertTriangle className="size-4 text-status-flagged" />
                )}
                {FlagMessages[selectedGroup.type] || selectedGroup.type}
              </DialogTitle>
              <DialogDescription>
                {selectedGroup.items.length} flag
                {selectedGroup.items.length !== 1 && "s"} of this type
              </DialogDescription>
            </DialogHeader>
            <ul className="flex flex-col gap-2">
              {selectedGroup.items.map((flag, i) => (
                <li
                  key={i}
                  className="rounded-md border border-border bg-muted/50 px-3 py-2 text-xs text-foreground"
                >
                  {flag.note || FlagMessages[flag.type] || flag.type}
                </li>
              ))}
            </ul>
          </DialogContent>
        )}
      </Dialog>
    </>
  );
}

const PlotHeaderCard = ({
  plotId,
  status,
  flaggedReason,
  lastCheckedBy,
  lastCheckedAt,
  attachmentCount,
  onBack,
  onMenuClick,
  activeTab,
  onTabChange,
}) => {
  const { errors, warnings } = splitFlags(flaggedReason);
  const hasFlags = errors.length > 0 || warnings.length > 0;

  return (
    <div className="flex w-full flex-col bg-white">
      {/* Header */}
      <div className="flex items-center gap-4 border-b border-border px-4 py-3">
        <button
          type="button"
          onClick={onBack}
          className="flex size-[42px] cursor-pointer items-center justify-center rounded-lg bg-muted transition-colors hover:bg-muted/80"
          aria-label="Go back"
        >
          <ChevronLeft className="size-4 text-foreground" />
        </button>
        <h2 className="text-base font-bold text-foreground">Plot data</h2>
      </div>

      {/* Content */}
      <div className="flex flex-col gap-4 px-4 pt-6">
        {/* Flag list */}
        {hasFlags && <FlagList flags={[...errors, ...warnings]} />}

        {/* Status row */}
        {status && (
          <div className="flex items-center justify-between">
            <StatusBadge status={status} />
            {onMenuClick && (
              <button
                type="button"
                onClick={onMenuClick}
                className="flex size-6 cursor-pointer items-center justify-center rounded text-foreground transition-colors hover:bg-muted"
                aria-label="More options"
              >
                <EllipsisVertical className="size-4" />
              </button>
            )}
          </div>
        )}

        {/* Plot ID */}

        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-1">
            <h2 className="text-xl text-foreground">Plot ID:&nbsp;</h2>
            <h2 className="text-xl font-bold text-foreground">
              {plotId ? `#${plotId}` : "—"}
            </h2>
          </div>
          {lastCheckedBy && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>Last checked by:</span>
              <span className="text-foreground">{lastCheckedBy}</span>
              {lastCheckedAt && (
                <>
                  <span className="size-1 rounded-full bg-muted-foreground" />
                  <span>{lastCheckedAt}</span>
                </>
              )}
            </div>
          )}
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={onTabChange}>
          <TabsList
            className={cn(
              "w-fit rounded-none border-0 divide-x-0 border-b border-border",
              "bg-transparent p-0",
            )}
          >
            <TabsTrigger
              value="details"
              className={cn(
                "rounded-none border-b-2 border-transparent px-3 py-2 text-xs",
                "data-[state=active]:border-b-green-600 data-[state=active]:bg-transparent data-[state=active]:text-green-600",
              )}
            >
              Details
            </TabsTrigger>
            <TabsTrigger
              value="attachments"
              className={cn(
                "rounded-none border-b-2 border-transparent px-3 py-2 text-xs",
                "data-[state=active]:border-b-green-600 data-[state=active]:bg-transparent data-[state=active]:text-green-600",
              )}
            >
              <Paperclip className="mr-1 size-3.5" />
              Attachments
              {attachmentCount > 0 && (
                <span className="ml-1">({attachmentCount})</span>
              )}
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
    </div>
  );
};

export default PlotHeaderCard;
