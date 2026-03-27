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
  AttachmentCell,
  TextCell,
  SortableHeader,
  getAriaSort,
} from "@/components/table-view";
import { PREFIX_PLOT_ID, EXCLUDED_QUESTION_NAMES } from "@/lib/constants";

const IMAGE_TYPES = new Set(["image"]);

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
  ordering,
  onSort,
  sortableFields = [],
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
        key: "kobo_id",
        header: (
          <SortableHeader
            columnKey="kobo_id"
            currentSort={ordering}
            onSort={onSort}
          >
            Plot ID
          </SortableHeader>
        ),
        ariaSort: getAriaSort("kobo_id", ordering),
        sticky: true,
        className: "max-w-[240px]",
        cell: (row) => (
          <TextCell className="text-foreground font-bold">
            {row.kobo_id ? `${PREFIX_PLOT_ID}${row.kobo_id}` : "—"}
          </TextCell>
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
        key: "reviewed_by",
        header: (
          <SortableHeader
            columnKey="reviewed_by"
            currentSort={ordering}
            onSort={onSort}
          >
            Reviewed by
          </SortableHeader>
        ),
        ariaSort: getAriaSort("reviewed_by", ordering),
        cell: (row) => <TextCell>{row.reviewed_by || "-"}</TextCell>,
      },
      {
        key: "start",
        header: (
          <SortableHeader
            columnKey="start"
            currentSort={ordering}
            onSort={onSort}
          >
            Start date
          </SortableHeader>
        ),
        ariaSort: getAriaSort("start", ordering),
        cell: (row) => (
          <TextCell>
            {row.start ? new Date(row.start).toLocaleDateString("en-GB") : null}
          </TextCell>
        ),
      },
      {
        key: "end",
        header: (
          <SortableHeader
            columnKey="end"
            currentSort={ordering}
            onSort={onSort}
          >
            End date
          </SortableHeader>
        ),
        ariaSort: getAriaSort("end", ordering),
        cell: (row) => (
          <TextCell>
            {row.end ? new Date(row.end).toLocaleDateString("en-GB") : null}
          </TextCell>
        ),
      },
      {
        key: "region",
        header: (
          <SortableHeader
            columnKey="region"
            currentSort={ordering}
            onSort={onSort}
          >
            Region
          </SortableHeader>
        ),
        ariaSort: getAriaSort("region", ordering),
        cell: (row) => <TextCell>{row.region}</TextCell>,
      },
      {
        key: "sub_region",
        header: (
          <SortableHeader
            columnKey="sub_region"
            currentSort={ordering}
            onSort={onSort}
          >
            Sub-region
          </SortableHeader>
        ),
        ariaSort: getAriaSort("sub_region", ordering),
        cell: (row) => <TextCell>{row.sub_region}</TextCell>,
      },
      {
        key: "area_ha",
        header: (
          <SortableHeader
            columnKey="area_ha"
            currentSort={ordering}
            onSort={onSort}
          >
            Area (ha)
          </SortableHeader>
        ),
        ariaSort: getAriaSort("area_ha", ordering),
        cell: (row) => (
          <TextCell>{row.area_ha != null ? row.area_ha : "-"}</TextCell>
        ),
      },
    ];

    const dynamic = dynamicQuestions.map((q) => ({
      key: q.name,
      header: sortableFields.includes(q.name) ? (
        <SortableHeader
          columnKey={q.name}
          currentSort={ordering}
          onSort={onSort}
        >
          {q.label}
        </SortableHeader>
      ) : (
        q.label
      ),
      ariaSort: sortableFields.includes(q.name)
        ? getAriaSort(q.name, ordering)
        : undefined,
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
  }, [dynamicQuestions, ordering, onSort, sortableFields]);

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
        <DialogContent className="sm:max-w-lg max-h-[90vh] flex flex-col">
          <DialogHeader className="shrink-0">
            <DialogTitle>{preview?.label}</DialogTitle>
            <p className="text-sm text-muted-foreground">
              {preview?.instanceName}
            </p>
          </DialogHeader>
          {preview?.url && (
            <div className="min-h-0 flex-1 overflow-y-auto">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={preview.url}
                alt={preview.label}
                className="w-full rounded-md object-contain"
              />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </DataTable>
  );
}
