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
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, Loader2 } from "lucide-react";

export function FormRegisterCard({ registerForm }) {
  const [assetUid, setAssetUid] = useState("");
  const [formName, setFormName] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [status, setStatus] = useState(null);

  async function handleRegister(e) {
    e.preventDefault();
    if (!assetUid.trim() || !formName.trim()) {
      return;
    }

    setIsRegistering(true);
    setStatus(null);
    try {
      await registerForm({
        assetUid: assetUid.trim(),
        name: formName.trim(),
      });
      setStatus({
        type: "success",
        message: `Form "${formName}" registered.`,
      });
      setAssetUid("");
      setFormName("");
    } catch (err) {
      const errData = err.response?.data;
      let message = "Failed to register form.";
      if (errData?.detail) {
        message = errData.detail;
      } else if (errData?.message) {
        message = errData.message;
      } else if (errData && typeof errData === "object") {
        const fieldErrors = Object.values(errData).flat().join(" ");
        if (fieldErrors) {
          message =
            fieldErrors.charAt(0).toUpperCase() + fieldErrors.slice(1);
        }
      }
      setStatus({ type: "error", message });
    } finally {
      setIsRegistering(false);
    }
  }

  return (
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
          className="flex flex-col gap-4 md:flex-row sm:items-start"
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
            <p className="text-xs text-muted-foreground">
              Find this in your KoboToolbox project URL or API settings.{" "}
              <a
                href="https://support.kobotoolbox.org/api.html#retrieving-your-project-asset-uid"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-foreground"
              >
                Learn how to get your Asset UID
              </a>
            </p>
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
            <p className="text-xs text-muted-foreground">
              A display name to identify this form in the dashboard
            </p>
          </div>
          <div className="pt-6">
            <Button
              type="submit"
              disabled={isRegistering}
              className="shrink-0"
            >
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
          </div>
        </form>

        {status && (
          <div
            role="alert"
            className={`mt-4 rounded-md p-3 text-sm ${
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
      </CardContent>
    </Card>
  );
}
