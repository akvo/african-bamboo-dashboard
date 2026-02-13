"use client";

import { useState } from "react";
import { useForms } from "@/hooks/useForms";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Plus, Loader2, RefreshCw } from "lucide-react";

export default function FormsPage() {
  const { forms, isLoading, registerForm, syncForm } = useForms();
  const [assetUid, setAssetUid] = useState("");
  const [formName, setFormName] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [syncingId, setSyncingId] = useState(null);
  const [status, setStatus] = useState(null);

  async function handleRegister(e) {
    e.preventDefault();
    if (!assetUid.trim() || !formName.trim()) return;

    setIsRegistering(true);
    setStatus(null);
    try {
      await registerForm({ assetUid: assetUid.trim(), name: formName.trim() });
      setStatus({ type: "success", message: `Form "${formName}" registered.` });
      setAssetUid("");
      setFormName("");
    } catch (err) {
      setStatus({
        type: "error",
        message:
          err.response?.data?.detail ||
          err.response?.data?.message ||
          "Failed to register form.",
      });
    } finally {
      setIsRegistering(false);
    }
  }

  async function handleSync(form) {
    setSyncingId(form.asset_uid);
    setStatus(null);
    try {
      const result = await syncForm(form.asset_uid);
      setStatus({
        type: "success",
        message: `Synced ${result.synced} submission(s), ${result.created} new.`,
      });
    } catch (err) {
      setStatus({
        type: "error",
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
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Forms</h1>
        <p className="text-sm text-muted-foreground">
          Manage your registered KoboToolbox forms
        </p>
      </div>

      {/* Register Form */}
      <Card>
        <CardHeader>
          <CardTitle>Register a Form</CardTitle>
          <CardDescription>
            Register a KoboToolbox form by its asset UID to sync submissions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleRegister}
            className="flex flex-col gap-4 sm:flex-row sm:items-end"
          >
            <div className="flex-1 space-y-2">
              <Label htmlFor="asset_uid">Asset UID</Label>
              <Input
                id="asset_uid"
                placeholder="e.g. aYRqYXmmPLFfbcwC2KAULa"
                value={assetUid}
                onChange={(e) => setAssetUid(e.target.value)}
                required
              />
            </div>
            <div className="flex-1 space-y-2">
              <Label htmlFor="form_name">Form Name</Label>
              <Input
                id="form_name"
                placeholder="e.g. Bamboo Plot Survey"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                required
              />
            </div>
            <Button type="submit" disabled={isRegistering} className="shrink-0">
              {isRegistering ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Registering...
                </>
              ) : (
                <>
                  <Plus className="size-4" />
                  Register
                </>
              )}
            </Button>
          </form>

          {status && (
            <div
              role="alert"
              className={`mt-4 rounded-md p-3 text-sm ${
                status.type === "success"
                  ? "bg-status-approved/10 text-status-approved"
                  : "bg-destructive/10 text-destructive"
              }`}
            >
              {status.message}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Forms Table */}
      <Card>
        <CardHeader>
          <CardTitle>Registered Forms</CardTitle>
          <CardDescription>
            {forms.length} form{forms.length !== 1 ? "s" : ""} registered
          </CardDescription>
        </CardHeader>
        <CardContent>
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
                      <TableCell className="font-medium">{form.name}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {form.asset_uid}
                      </TableCell>
                      <TableCell className="text-right">
                        {form.submission_count ?? 0}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {form.last_sync_timestamp
                          ? new Date(form.last_sync_timestamp).toLocaleString()
                          : "Never"}
                      </TableCell>
                      <TableCell className="text-right">
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
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
