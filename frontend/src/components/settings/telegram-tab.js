"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import api from "@/lib/api";
import { useForms } from "@/hooks/useForms";
import { mergeRegionOptions, uncoveredRegions } from "@/lib/telegram-regions";
import { MultiSelectDropdown } from "@/components/multi-select-dropdown";
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
import { Loader2, Plus, RefreshCw, Trash2 } from "lucide-react";

export default function TelegramTab() {
  // Stable row keys: Select/dropdown keep UI state per row.
  const keySeq = useRef(0);
  const withKeys = (data) => ({
    ...data,
    groups: data.groups.map((g) => ({ ...g, _key: ++keySeq.current })),
  });
  const { forms } = useForms();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [groups, setGroups] = useState([]);
  // An outage used to look identical to "no groups
  // configured": the catch below emptied the list and
  // the UI silently fell back to a bare chat-ID box.
  const [groupsError, setGroupsError] = useState(null);
  const [loadingGroups, setLoadingGroups] = useState(false);
  const [regionOptions, setRegionOptions] = useState([]);
  const [config, setConfig] = useState({
    enabled: false,
    bot_token: "",
    groups: [],
  });

  const fetchGroups = useCallback(async (token) => {
    if (!token) {
      return;
    }
    setLoadingGroups(true);
    setGroupsError(null);
    try {
      const { data } = await api.get("/v1/settings/telegram/groups/", {
        params: { bot_token: token },
      });
      setGroups(data);
    } catch (err) {
      setGroups([]);
      setGroupsError(
        err?.response?.data?.detail ||
          "Could not reach Telegram. Check the bot token and " +
            "the server's network access, then try again.",
      );
    } finally {
      setLoadingGroups(false);
    }
  }, []);

  const fetchConfig = useCallback(async () => {
    try {
      const { data } = await api.get("/v1/settings/telegram/");
      setConfig(withKeys(data));
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

  // ponytail: useForms reads only the first page of forms
  // (PAGE_SIZE 10); fetch every page if a site ever has
  // more (spec D-3).
  useEffect(() => {
    let cancelled = false;
    Promise.all(
      forms.map((f) =>
        api
          .get("/v1/odk/plots/filter_options/", {
            params: { form_id: f.asset_uid },
          })
          .then(({ data }) => ({
            formName: f.name,
            regions: data.regions || [],
          }))
          // One failing form must not hide the others.
          .catch(() => ({ formName: f.name, regions: [] })),
      ),
    ).then((perForm) => {
      if (!cancelled) {
        setRegionOptions(mergeRegionOptions(perForm));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [forms]);

  const updateGroup = (index, patch) =>
    setConfig((prev) => ({
      ...prev,
      groups: prev.groups.map((g, i) =>
        i === index ? { ...g, ...patch } : g,
      ),
    }));

  const toggleRegion = (index, value) => {
    const { regions } = config.groups[index];
    updateGroup(index, {
      regions: regions.includes(value)
        ? regions.filter((r) => r !== value)
        : [...regions, value],
    });
  };

  const addGroup = () =>
    setConfig((prev) => ({
      ...prev,
      groups: [
        ...prev.groups,
        { chat_id: "", title: "", regions: [], _key: ++keySeq.current },
      ],
    }));

  const removeGroup = (index) =>
    setConfig((prev) => ({
      ...prev,
      groups: prev.groups.filter((_, i) => i !== index),
    }));

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const { data } = await api.put("/v1/settings/telegram/", {
        ...config,
        // A row with no group picked yet is not a group.
        groups: config.groups.filter((g) => g.chat_id.trim()),
      });
      setConfig(withKeys(data));
    } catch (err) {
      const msg = err?.response?.data?.groups?.[0];
      setSaveError(typeof msg === "string" ? msg : "Could not save settings.");
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
  const discovered = Object.fromEntries(groups.map((g) => [g.id, g]));
  // Configured rows getChat could not resolve still need
  // to show in their own dropdown.
  const groupChoices = [
    ...groups,
    ...config.groups
      .filter((g) => g.chat_id && !discovered[g.chat_id])
      .map((g) => ({ id: g.chat_id, title: g.title || "Unknown group" })),
  ];
  const badgeFor = (value) =>
    regionOptions.find((o) => o.value === value)?.badge || value;
  const uncovered = uncoveredRegions(regionOptions, config.groups);

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
                title="Re-sync groups"
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
              on Telegram, send <code>/newbot</code>, and paste the token. Then
              click Re-sync to load groups.
            </p>
          </div>

          {groupsError && (
            <p
              role="alert"
              className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700"
            >
              {groupsError}
            </p>
          )}

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label>Groups</Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={disabled}
                onClick={addGroup}
              >
                <Plus className="size-4" />
                Add group
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Each rejection goes to every group whose regions include the
              plot&apos;s region. Leave regions empty to receive all regions. A
              newly added group only appears in the list after the bot is in
              it, someone posts a message there, and you click Re-sync.
            </p>

            {config.groups.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No groups yet. Rejection alerts are not sent until you add
                one.
              </p>
            )}

            {config.groups.map((g, i) => {
              const count = discovered[g.chat_id]?.member_count;
              return (
                <div key={g._key} className="space-y-2 rounded-md border p-3">
                  <div className="flex gap-2">
                    {groupChoices.length > 0 ? (
                      <Select
                        disabled={disabled}
                        value={g.chat_id || undefined}
                        onValueChange={(val) => updateGroup(i, { chat_id: val })}
                      >
                        <SelectTrigger
                          className="w-full"
                          aria-label="Telegram group"
                        >
                          <SelectValue placeholder="Select a group..." />
                        </SelectTrigger>
                        <SelectContent>
                          {groupChoices.map((c) => (
                            <SelectItem key={c.id} value={c.id}>
                              {c.title} ({c.id})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Input
                        aria-label="Telegram chat ID"
                        placeholder="-100123456789"
                        disabled={disabled}
                        value={g.chat_id}
                        onChange={(e) =>
                          updateGroup(i, { chat_id: e.target.value })
                        }
                      />
                    )}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      disabled={disabled}
                      onClick={() => removeGroup(i)}
                      title="Remove group"
                      className="shrink-0"
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {typeof count === "number" ? `${count} members` : "—"}
                  </p>
                  <MultiSelectDropdown
                    placeholder="All regions"
                    items={regionOptions}
                    selected={g.regions}
                    onToggle={(value) => toggleRegion(i, value)}
                    getItemKey={(o) => o.value}
                    getItemLabel={(o) => o.label}
                    getBadgeLabel={badgeFor}
                    scrollable
                  />
                </div>
              );
            })}

            {uncovered.length > 0 && (
              <p
                role="alert"
                className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-700"
              >
                No group covers {uncovered.map((o) => o.badge).join(", ")}.
                Rejections from these regions will show as failed until a group
                covers them.
              </p>
            )}
          </div>
        </div>

        {saveError && (
          <p role="alert" className="text-xs text-destructive">
            {saveError}
          </p>
        )}
        <Button onClick={handleSave} disabled={saving}>
          {saving && <Loader2 className="size-4 animate-spin" />}
          Save changes
        </Button>
      </CardContent>
    </Card>
  );
}
