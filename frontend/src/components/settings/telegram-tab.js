"use client";

import { useState, useEffect, useCallback } from "react";
import api from "@/lib/api";
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
import { Switch } from "@/components/ui/switch";
import { Loader2 } from "lucide-react";

export default function TelegramTab() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState({
    enabled: false,
    bot_token: "",
    supervisor_group_id: "",
    enumerator_group_id: "",
  });

  const fetchConfig = useCallback(async () => {
    try {
      const { data } = await api.get("/v1/settings/telegram/");
      setConfig(data);
    } catch {
      // silently fail, keep defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const { data } = await api.put("/v1/settings/telegram/", config);
      setConfig(data);
    } catch {
      // TODO: toast error
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const disabled = !config.enabled;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Telegram Notifications</CardTitle>
        <CardDescription>
          Configure Telegram bot for plot rejection notifications
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label htmlFor="telegram-enabled">Enable notifications</Label>
            <p className="text-xs text-muted-foreground">
              Send rejection alerts to Telegram groups
            </p>
          </div>
          <Switch
            id="telegram-enabled"
            checked={config.enabled}
            onCheckedChange={(checked) =>
              setConfig((prev) => ({ ...prev, enabled: checked }))
            }
          />
        </div>

        <div className={`space-y-4 ${disabled ? "opacity-50" : ""}`}>
          <div className="space-y-2">
            <Label htmlFor="bot-token">Bot Token</Label>
            <Input
              id="bot-token"
              type="password"
              placeholder="123456:ABC-DEF..."
              disabled={disabled}
              value={config.bot_token}
              onChange={(e) =>
                setConfig((prev) => ({
                  ...prev,
                  bot_token: e.target.value,
                }))
              }
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="supervisor-group">Supervisor Group ID</Label>
            <Input
              id="supervisor-group"
              placeholder="-100123456789"
              disabled={disabled}
              value={config.supervisor_group_id}
              onChange={(e) =>
                setConfig((prev) => ({
                  ...prev,
                  supervisor_group_id: e.target.value,
                }))
              }
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="enumerator-group">Enumerator Group ID</Label>
            <Input
              id="enumerator-group"
              placeholder="-100987654321"
              disabled={disabled}
              value={config.enumerator_group_id}
              onChange={(e) =>
                setConfig((prev) => ({
                  ...prev,
                  enumerator_group_id: e.target.value,
                }))
              }
            />
          </div>
        </div>

        <Button onClick={handleSave} disabled={saving}>
          {saving && <Loader2 className="size-4 animate-spin" />}
          Save changes
        </Button>
      </CardContent>
    </Card>
  );
}
