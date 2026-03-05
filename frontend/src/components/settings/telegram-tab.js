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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, RefreshCw } from "lucide-react";

export default function TelegramTab() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [groups, setGroups] = useState([]);
  const [loadingGroups, setLoadingGroups] = useState(false);
  const [config, setConfig] = useState({
    enabled: false,
    bot_token: "",
    supervisor_group_id: "",
    enumerator_group_id: "",
  });

  const fetchGroups = useCallback(async (token) => {
    if (!token) return;
    setLoadingGroups(true);
    try {
      const params = token ? { bot_token: token } : {};
      const { data } = await api.get("/v1/settings/telegram/groups/", {
        params,
      });
      setGroups(data);
    } catch {
      setGroups([]);
    } finally {
      setLoadingGroups(false);
    }
  }, []);

  const fetchConfig = useCallback(async () => {
    try {
      const { data } = await api.get("/v1/settings/telegram/");
      setConfig(data);
      if (data.bot_token) {
        fetchGroups(data.bot_token);
      }
    } catch {
      // silently fail, keep defaults
    } finally {
      setLoading(false);
    }
  }, [fetchGroups]);

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
            <div className="flex gap-2">
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
                className="flex-1"
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                disabled={disabled || !config.bot_token || loadingGroups}
                onClick={() => fetchGroups(config.bot_token)}
                title="Fetch groups from bot"
              >
                <RefreshCw
                  className={`size-4 ${loadingGroups ? "animate-spin" : ""}`}
                />
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Message{" "}
              <a
                href="https://t.me/BotFather"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                @BotFather
              </a>{" "}
              on Telegram, send <code>/newbot</code>, and paste the token.
              Then click refresh to load groups.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="supervisor-group">Supervisor Group</Label>
            {groups.length > 0 ? (
              <Select
                disabled={disabled}
                value={config.supervisor_group_id}
                onValueChange={(val) =>
                  setConfig((prev) => ({
                    ...prev,
                    supervisor_group_id: val,
                  }))
                }
              >
                <SelectTrigger id="supervisor-group" className="w-full">
                  <SelectValue placeholder="Select a group..." />
                </SelectTrigger>
                <SelectContent>
                  {groups.map((g) => (
                    <SelectItem key={g.id} value={g.id}>
                      {g.title} ({g.id})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
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
            )}
            {groups.length === 0 && (
              <p className="text-xs text-muted-foreground">
                Enter a bot token and click refresh to load available groups.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="enumerator-group">Enumerator Group</Label>
            {groups.length > 0 ? (
              <Select
                disabled={disabled}
                value={config.enumerator_group_id}
                onValueChange={(val) =>
                  setConfig((prev) => ({
                    ...prev,
                    enumerator_group_id: val,
                  }))
                }
              >
                <SelectTrigger id="enumerator-group" className="w-full">
                  <SelectValue placeholder="Select a group..." />
                </SelectTrigger>
                <SelectContent>
                  {groups.map((g) => (
                    <SelectItem key={g.id} value={g.id}>
                      {g.title} ({g.id})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
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
            )}
            {groups.length === 0 && (
              <p className="text-xs text-muted-foreground">
                Can be the same group as Supervisor.
              </p>
            )}
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
