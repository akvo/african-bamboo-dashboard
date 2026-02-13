"use client";

import { useAuth } from "@/context/AuthContext";
import { logout } from "@/app/actions/auth";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { LogOut } from "lucide-react";

export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Your account profile and preferences
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>
            Your KoboToolbox account information (read-only)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Label className="text-muted-foreground">Name</Label>
            <p className="text-sm font-medium">{user?.name || "-"}</p>
          </div>
          <Separator />
          <div className="space-y-1">
            <Label className="text-muted-foreground">Email</Label>
            <p className="text-sm font-medium">{user?.email || "-"}</p>
          </div>
          <Separator />
          <div className="space-y-1">
            <Label className="text-muted-foreground">KoboToolbox Username</Label>
            <p className="text-sm font-medium">{user?.kobo_username || "-"}</p>
          </div>
          <Separator />
          <div className="space-y-1">
            <Label className="text-muted-foreground">KoboToolbox Server</Label>
            <p className="text-sm font-medium">{user?.kobo_url || "-"}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Session</CardTitle>
          <CardDescription>Manage your current session</CardDescription>
        </CardHeader>
        <CardContent>
          <form action={logout}>
            <Button variant="destructive" type="submit">
              <LogOut className="size-4" />
              Sign out
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
