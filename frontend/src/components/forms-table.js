"use client";

import { useState } from "react";
import { logout } from "@/app/actions/auth";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Loader2, RefreshCw, Settings } from "lucide-react";

export function FormsTable({
  forms,
  isLoading,
  syncForm,
  onConfigureClick,
}) {
  const [syncingId, setSyncingId] = useState(null);
  const [status, setStatus] = useState(null);

  async function handleSync(form) {
    setSyncingId(form.asset_uid);
    setStatus(null);
    try {
      const result = await syncForm(form.asset_uid);
      const parts = [];
      parts.push(`Synced ${result.synced} submission(s)`);
      if (
        result.plots_created !== undefined ||
        result.plots_updated !== undefined
      ) {
        const plotsCreated = result.plots_created || 0;
        const plotsUpdated = result.plots_updated || 0;
        parts.push(`${plotsCreated} created, ${plotsUpdated} updated`);
      }
      setStatus({
        type: "success",
        message: parts.join(". ") + ".",
      });
    } catch (err) {
      const isKoboAuth =
        err.response?.data?.error_type === "kobo_unauthorized";
      setStatus({
        type: isKoboAuth ? "kobo_unauthorized" : "error",
        message:
          err.response?.data?.message ||
          err.response?.data?.detail ||
          "Failed to sync form.",
      });
    } finally {
      setSyncingId(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Registered Forms</CardTitle>
        <CardDescription>
          {forms.length} form{forms.length !== 1 ? "s" : ""} registered
        </CardDescription>
      </CardHeader>
      <CardContent>
        {status && (
          <div
            role="alert"
            className={`mb-4 rounded-md p-3 text-sm ${
              status.type === "success"
                ? "bg-status-approved/10 text-status-approved"
                : status.type === "kobo_unauthorized"
                  ? "bg-amber-500/10 text-amber-700 dark:text-amber-400"
                  : "bg-destructive/10 text-destructive"
            }`}
          >
            {status.message}
            {status.type === "kobo_unauthorized" && (
              <button
                onClick={() => logout()}
                className="underline font-medium hover:opacity-80 cursor-pointer ml-2"
              >
                Go to login
              </button>
            )}
          </div>
        )}

        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : forms.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No forms registered yet. Register a form above to get started.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Asset UID</TableHead>
                  <TableHead className="text-right">Submissions</TableHead>
                  <TableHead>Last Synced</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {forms.map((form) => (
                  <TableRow key={form.asset_uid}>
                    <TableCell className="font-medium">
                      {form.name}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {form.asset_uid}
                    </TableCell>
                    <TableCell className="text-right">
                      {form.submission_count ?? 0}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {form.last_sync_timestamp
                        ? new Date(
                            form.last_sync_timestamp,
                          ).toLocaleString()
                        : "Never"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onConfigureClick(form)}
                        >
                          <Settings className="size-4" />
                          Configure
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={syncingId === form.asset_uid}
                          onClick={() => handleSync(form)}
                        >
                          {syncingId === form.asset_uid ? (
                            <Loader2 className="size-4 animate-spin" />
                          ) : (
                            <RefreshCw className="size-4" />
                          )}
                          Sync
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
