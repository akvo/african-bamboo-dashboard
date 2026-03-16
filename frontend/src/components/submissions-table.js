"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { StatusBadge } from "@/components/status-badge";
import {
  DataTable,
  TwoLineCell,
  AttachmentCell,
  TextCell,
} from "@/components/table-view";

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

export function SubmissionsTable({
  data,
  isLoading,
  plots = [],
  questions = [],
}) {
  const router = useRouter();
  const [preview, setPreview] = useState(null);

  const plotBySubmission = useMemo(
    () => new Map(plots.map((p) => [p.submission_uuid, p.uuid])),
    [plots],
  );

  const dynamicQuestions = useMemo(
    () => questions.filter((q) => !EXCLUDED_QUESTION_NAMES.includes(q.name)),
    [questions],
  );

  const columns = useMemo(() => {
    const base = [
      {
        key: "plot_name",
        header: "Plot ID",
        sticky: true,
        className: "max-w-[240px]",
        cell: (row) => (
          <TwoLineCell primary={row.plot_name} secondary={row.instance_name} />
        ),
      },
      {
        key: "status",
        header: "Status",
        cell: (row) => (
          <StatusBadge status={getApprovalLabel(row.approval_status)} />
        ),
      },
      {
        key: "start_date",
        header: "Start date",
        cell: (row) => (
          <TextCell>
            {row.submission_time
              ? new Date(row.submission_time).toLocaleDateString("en-GB")
              : null}
          </TextCell>
        ),
      },
      {
        key: "enumerator",
        header: "Enumerator",
        cell: (row) => (
          <TextCell>{row.enumerator || row.submitted_by}</TextCell>
        ),
      },
      {
        key: "region",
        header: "Region",
        cell: (row) => <TextCell>{row.region}</TextCell>,
      },
      {
        key: "sub_region",
        header: "Sub-region",
        cell: (row) => <TextCell>{row.sub_region}</TextCell>,
      },
    ];

    const dynamic = dynamicQuestions.map((q) => ({
      key: q.name,
      header: q.label,
      headerClassName: "max-w-[250px] truncate",
      className: "max-w-[250px] truncate text-muted-foreground",
      cell: (row) => {
        const resolved = row.resolved_data || {};
        const attachments = resolved._attachments;

        if (IMAGE_TYPES.has(q.type)) {
          const url = getAttachmentUrl(attachments, q.name);
          return (
            <AttachmentCell
              url={url}
              filename={resolved?.[q.name]}
              onPreview={() =>
                setPreview({
                  url,
                  label: q.label,
                  instanceName: row.instance_name,
                })
              }
            />
          );
        }
        return (
          <span
            title={
              resolved[q.name] != null ? String(resolved[q.name]) : undefined
            }
          >
            {resolved?.[q.name] || "-"}
          </span>
        );
      },
    }));

    return [...base, ...dynamic];
  }, [dynamicQuestions]);

  return (
    <DataTable
      columns={columns}
      data={data}
      rowKey={(row) => row.uuid}
      isLoading={isLoading}
      emptyMessage="No submissions found."
      onRowClick={(row) => {
        const plotUuid = plotBySubmission.get(row.uuid);
        if (plotUuid) router.push(`/dashboard/map?plot=${plotUuid}`);
      }}
      rowClassName={(row) =>
        plotBySubmission.has(row.uuid) ? "cursor-pointer" : "opacity-60"
      }
      rowTitle={(row) =>
        plotBySubmission.has(row.uuid)
          ? "View on map"
          : "No plot geometry available"
      }
    >
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
    </DataTable>
  );
}
