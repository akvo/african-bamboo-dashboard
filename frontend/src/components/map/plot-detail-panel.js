"use client";

import { useState, useEffect } from "react";
import { ArrowLeft, MapPin, Edit3, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/status-badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getPlotStatus } from "@/lib/plot-utils";
import api from "@/lib/api";

function MetadataRow({ label, value }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm font-medium">{value || "—"}</p>
    </div>
  );
}

export default function PlotDetailPanel({
  plot,
  onBack,
  onApprove,
  onReject,
  onStartEditing,
}) {
  const [submission, setSubmission] = useState(null);
  const [isLoadingSub, setIsLoadingSub] = useState(false);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (!plot?.submission_uuid) {
      setSubmission(null);
      setNotes("");
      return;
    }
    let cancelled = false;
    setIsLoadingSub(true);
    api
      .get(`/v1/odk/submissions/${plot.submission_uuid}/`)
      .then((res) => {
        if (!cancelled) {
          setSubmission(res.data);
          setNotes(res.data.reviewer_notes || "");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSubmission(null);
          setNotes("");
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoadingSub(false);
      });
    return () => {
      cancelled = true;
    };
  }, [plot?.submission_uuid]);

  if (!plot) return null;

  const status = getPlotStatus(plot);
  const resolved = submission?.resolved_data || {};
  const hasGeometry =
    plot.min_lat != null &&
    plot.max_lat != null &&
    plot.min_lon != null &&
    plot.max_lon != null;
  const centerLat = hasGeometry
    ? ((plot.min_lat + plot.max_lat) / 2).toFixed(6)
    : null;
  const centerLon = hasGeometry
    ? ((plot.min_lon + plot.max_lon) / 2).toFixed(6)
    : null;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border px-4 py-3">
        <button
          type="button"
          onClick={onBack}
          className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground transition-colors duration-200 hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Plot data
        </button>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-4 p-4">
          {/* Title */}
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold">{plot.plot_name}</h2>
              <StatusBadge status={status} />
            </div>
            <p className="text-sm text-muted-foreground">
              {plot.instance_name}
            </p>
          </div>

          {/* Flagged reason banner */}
          {plot.flagged_for_review && plot.flagged_reason && (
            <div className="flex items-start gap-2 rounded-md border border-status-flagged/30 bg-status-flagged/10 px-3 py-2">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-status-flagged" />
              <p className="text-sm text-status-flagged">
                {plot.flagged_reason}
              </p>
            </div>
          )}

          {/* Metadata grid */}
          {isLoadingSub ? (
            <div className="grid grid-cols-2 gap-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <MetadataRow label="Region" value={plot.region} />
              <MetadataRow label="Sub-region" value={plot.sub_region} />
              <MetadataRow label="Enumerator" value={resolved.enumerator_id} />
              <MetadataRow
                label="Boundary method"
                value={resolved["boundary_mapping/boundary_method"]}
              />
              <MetadataRow label="Farmer" value={resolved.full_name} />
              <MetadataRow label="Age" value={resolved.age_of_farmer} />
              <MetadataRow label="Phone" value={resolved.Phone_Number} />
              <MetadataRow label="Points" value={resolved.numpoints} />
            </div>
          )}

          {/* Coordinates */}
          {hasGeometry ? (
            <div className="flex items-center gap-2 rounded-md bg-muted px-3 py-2">
              <MapPin className="size-4 text-muted-foreground" />
              <span className="text-sm">
                {centerLat}, {centerLon}
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-2 rounded-md bg-muted px-3 py-2">
              <MapPin className="size-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                No geometry data
              </span>
            </div>
          )}

          {/* Edit geometry button */}
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            disabled={!hasGeometry}
            onClick={onStartEditing}
          >
            <Edit3 className="mr-2 size-4" />
            Fix Geometry
          </Button>

          {/* Notes */}
          <div className="space-y-2">
            <label htmlFor="plot-notes" className="text-sm font-medium">
              Notes
            </label>
            <Textarea
              id="plot-notes"
              placeholder="Add notes for the enumerator..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="min-h-20"
            />
          </div>
        </div>
      </ScrollArea>

      {/* Action buttons */}
      {["pending", "flagged"].includes(status) && (
        <div className="flex gap-2 border-t border-border p-4">
          <Button
            className="flex-1 bg-status-approved text-white hover:bg-status-approved/90"
            onClick={() => onApprove(notes)}
          >
            Approve
          </Button>
          <Button
            variant="destructive"
            className="flex-1"
            onClick={() => onReject(notes)}
          >
            Reject
          </Button>
        </div>
      )}
    </div>
  );
}
