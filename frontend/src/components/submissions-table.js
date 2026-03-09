"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ImageIcon } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/status-badge";

const IMAGE_TYPES = new Set(["image"]);
const EXCLUDED_QUESTION_NAMES = ["region", "region_specify"];

function getApprovalLabel(approvalStatus) {
  if (approvalStatus === 1) return "approved";
  if (approvalStatus === 2) return "rejected";
  return "pending";
}

function getAttachmentUrl(attachments, questionName) {
  if (!attachments?.length) return null;
  const att = attachments.find((a) => a.question_xpath === questionName);
  return att?.local_url || null;
}

function ImageCell({ url, label, instanceName, onPreview }) {
  if (!url) {
    return <span className="text-muted-foreground">-</span>;
  }
  return (
    <button
      type="button"
      className="flex cursor-pointer items-center gap-1.5 text-sm text-primary hover:underline"
      onClick={(e) => {
        e.stopPropagation();
        onPreview({ url, label, instanceName });
      }}
    >
      <ImageIcon className="size-4 shrink-0" />
      <span>View</span>
    </button>
  );
}

export function SubmissionsTable({
  data,
  isLoading,
  plots = [],
  questions = [],
}) {
  const router = useRouter();
  const [preview, setPreview] = useState(null);
  const plotBySubmission = new Map(
    plots.map((p) => [p.submission_uuid, p.uuid]),
  );
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="py-12 text-center text-muted-foreground">
        No submissions found.
      </div>
    );
  }

  return (
    <>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="sticky left-0 z-10 bg-muted">
                Plot name
              </TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Start date</TableHead>
              <TableHead>Enumerator</TableHead>
              <TableHead>Region</TableHead>
              <TableHead>Sub-region</TableHead>
              {questions
                .filter((q) => !EXCLUDED_QUESTION_NAMES.includes(q.name))
                .map((q) => (
                  <TableHead key={q.name} className="max-w-[250px] truncate">
                    {q.label}
                  </TableHead>
                ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row) => {
              const plotUuid = plotBySubmission.get(row.uuid);
              const resolved = row.resolved_data || {};
              const attachments = resolved._attachments;
              return (
                <TableRow
                  key={row.uuid}
                  onClick={() => {
                    if (plotUuid)
                      router.push(`/dashboard/map?plot=${plotUuid}`);
                  }}
                  className={plotUuid ? "cursor-pointer" : "opacity-60"}
                  title={
                    plotUuid ? "View on map" : "No plot geometry available"
                  }
                >
                  <TableCell className="sticky left-0 z-10 max-w-[240px] bg-background">
                    <p className="truncate text-sm font-medium text-foreground">
                      {row.plot_name}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {row.instance_name}
                    </p>
                  </TableCell>
                  <TableCell>
                    <StatusBadge
                      status={getApprovalLabel(row.approval_status)}
                    />
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground">
                    {row.submission_time
                      ? new Date(row.submission_time).toLocaleDateString()
                      : "-"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    {row.enumerator || row.submitted_by || "-"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    {row.region || "-"}
                  </TableCell>
                  <TableCell className="whitespace-nowrap">
                    {row.sub_region || "-"}
                  </TableCell>
                  {questions
                    .filter((q) => !EXCLUDED_QUESTION_NAMES.includes(q.name))
                    .map((q) => (
                      <TableCell
                        key={q.name}
                        className="max-w-[250px] truncate text-muted-foreground"
                        title={
                          !IMAGE_TYPES.has(q.type) && resolved[q.name] != null
                            ? String(resolved[q.name])
                            : undefined
                        }
                      >
                        {IMAGE_TYPES.has(q.type) ? (
                          <ImageCell
                            url={getAttachmentUrl(attachments, q.name)}
                            label={q.label}
                            instanceName={row.instance_name}
                            onPreview={setPreview}
                          />
                        ) : (
                          resolved?.[q.name] || "-"
                        )}
                      </TableCell>
                    ))}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <Dialog open={!!preview} onOpenChange={() => setPreview(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{preview?.label}</DialogTitle>
            <p className="text-sm text-muted-foreground">
              {preview?.instanceName}
            </p>
          </DialogHeader>
          {preview?.url && (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={preview.url}
              alt={preview.label}
              className="w-full rounded-md"
            />
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
