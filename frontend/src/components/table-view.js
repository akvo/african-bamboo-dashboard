"use client";

import React from "react";
import { ArrowDown, FileIcon } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * Reusable column-driven data table.
 *
 * @param {Object} props
 * @param {Array<{
 *   key: string,
 *   header: React.ReactNode,
 *   cell: (row: any) => React.ReactNode,
 *   className?: string,
 *   headerClassName?: string,
 *   sticky?: boolean,
 * }>} props.columns
 * @param {any[]} props.data
 * @param {(row: any) => string} props.rowKey
 * @param {boolean} [props.isLoading]
 * @param {string} [props.emptyMessage]
 * @param {(row: any) => void} [props.onRowClick]
 * @param {(row: any) => string} [props.rowClassName]
 * @param {(row: any) => string} [props.rowTitle]
 * @param {React.ReactNode} [props.children] - Extra content rendered after the table (e.g. dialogs)
 */
export function DataTable({
  columns,
  data,
  rowKey,
  isLoading = false,
  emptyMessage = "No data found.",
  onRowClick,
  rowClassName,
  rowTitle,
  children,
}) {
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
        {emptyMessage}
      </div>
    );
  }

  return (
    <>
      <div className="overflow-x-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead
                  key={col.key}
                  className={
                    col.sticky
                      ? `sticky left-0 z-10 bg-muted ${col.headerClassName || ""}`
                      : col.headerClassName
                  }
                  style={{
                    fontSize: 12,
                  }}
                >
                  {col.header}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row) => (
              <TableRow
                key={rowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={rowClassName?.(row)}
                title={rowTitle?.(row)}
              >
                {columns.map((col) => (
                  <TableCell
                    key={col.key}
                    className={
                      col.sticky
                        ? `sticky left-0 z-10 bg-background ${col.className || ""}`
                        : col.className
                    }
                  >
                    {col.cell(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {children}
    </>
  );
}

/* ── Reusable cell helpers ── */

export function SortableHeader({ children }) {
  return (
    <div className="flex items-center gap-1">
      <span>{children}</span>
      <ArrowDown className="size-3.5 text-muted-foreground" />
    </div>
  );
}

export function TwoLineCell({ primary, secondary }) {
  return (
    <div className="flex flex-col">
      <span className="truncate text-sm font-medium text-foreground">
        {primary}
      </span>
      <span className="truncate text-sm text-muted-foreground">
        {secondary}
      </span>
    </div>
  );
}

export function AttachmentCell({ filename, url, onPreview }) {
  if (!url) {
    return <span className="text-muted-foreground">-</span>;
  }
  return (
    <button
      type="button"
      className="flex cursor-pointer items-center gap-1.5 text-sm text-primary hover:underline"
      onClick={(e) => {
        e.stopPropagation();
        onPreview?.();
      }}
    >
      <span className="rounded-full bg-status-approved/5 size-9 flex items-center justify-center">
        <FileIcon className="size-4 text-status-approved" />
      </span>

      <span className="truncate text-sm text-foreground">
        {filename || "View"}
      </span>
    </button>
  );
}

export function TextCell({ children, className = "text-muted-foreground" }) {
  return (
    <span className={cn("whitespace-nowrap text-sm", className)}>
      {children || "-"}
    </span>
  );
}

export default DataTable;
