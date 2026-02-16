"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/status-badge";

function getApprovalLabel(approvalStatus) {
  if (approvalStatus === 1) return "approved";
  if (approvalStatus === 2) return "rejected";
  return "pending";
}

export function SubmissionsTable({ data, isLoading }) {
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
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Plot name</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Start date</TableHead>
            <TableHead>End date</TableHead>
            <TableHead>Enumerator</TableHead>
            <TableHead>Region</TableHead>
            <TableHead>Woreda</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((row) => (
            <TableRow key={row.uuid}>
              <TableCell>
                <div className="font-medium">
                  {row.instance_name || "Unnamed"}
                </div>
              </TableCell>
              <TableCell>
                <StatusBadge status={getApprovalLabel(row.approval_status)} />
              </TableCell>
              <TableCell className="text-muted-foreground">
                {row.submission_time
                  ? new Date(row.submission_time).toLocaleDateString()
                  : "-"}
              </TableCell>
              <TableCell className="text-muted-foreground">-</TableCell>
              <TableCell>{row.submitted_by || "-"}</TableCell>
              <TableCell>{row.region || "-"}</TableCell>
              <TableCell>{row.woreda || "-"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
