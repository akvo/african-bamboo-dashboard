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
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Plus, Loader2, RefreshCw, Settings, ChevronDown } from "lucide-react";

export default function FormsPage() {
  const {
    forms,
    isLoading,
    registerForm,
    syncForm,
    updateForm,
    fetchFormFields,
  } = useForms();
  const [assetUid, setAssetUid] = useState("");
  const [formName, setFormName] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [syncingId, setSyncingId] = useState(null);
  const [status, setStatus] = useState(null);

  // Field mapping dialog state
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [configForm, setConfigForm] = useState(null);
  const [formFields, setFormFields] = useState([]);
  const [isLoadingFields, setIsLoadingFields] = useState(false);
  const [isSavingMapping, setIsSavingMapping] = useState(false);
  const [mappingStatus, setMappingStatus] = useState(null);

  // Field mapping values
  const [polygonFields, setPolygonFields] = useState([]);
  const [regionFields, setRegionFields] = useState([]);
  const [subRegionFields, setSubRegionFields] = useState([]);
  const [plotNameFields, setPlotNameFields] = useState([]);

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
      const errData = err.response?.data;
      let message = "Failed to register form.";
      if (errData?.detail) {
        message = errData.detail;
      } else if (errData?.message) {
        message = errData.message;
      } else if (errData && typeof errData === "object") {
        const fieldErrors = Object.values(errData).flat().join(" ");
        if (fieldErrors) {
          message = fieldErrors;
          // capitalize first letter
          message = message.charAt(0).toUpperCase() + message.slice(1);
        }
      }
      setStatus({ type: "error", message });
    } finally {
      setIsRegistering(false);
    }
  }

  async function handleSync(form) {
    setSyncingId(form.asset_uid);
    setStatus(null);
    try {
      const result = await syncForm(form.asset_uid);
      const parts = [];
      parts.push(
        `Synced ${result.synced} submission(s), ${result.created} new`,
      );
      if (
        result.plots_created !== undefined ||
        result.plots_updated !== undefined
      ) {
        const plotsCreated = result.plots_created || 0;
        const plotsUpdated = result.plots_updated || 0;
        parts.push(`${plotsCreated} plot(s) created, ${plotsUpdated} updated`);
      }
      setStatus({
        type: "success",
        message: parts.join(". ") + ".",
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

  async function handleConfigureClick(form) {
    setConfigForm(form);
    setConfigDialogOpen(true);
    setMappingStatus(null);

    // Pre-populate existing values
    setPolygonFields(
      form.polygon_field
        ? form.polygon_field
            .split(",")
            .map((f) => f.trim())
            .filter(Boolean)
        : [],
    );
    setRegionFields(
      form.region_field
        ? form.region_field
            .split(",")
            .map((f) => f.trim())
            .filter(Boolean)
        : [],
    );
    setSubRegionFields(
      form.sub_region_field
        ? form.sub_region_field
            .split(",")
            .map((f) => f.trim())
            .filter(Boolean)
        : [],
    );
    setPlotNameFields(
      form.plot_name_field
        ? form.plot_name_field
            .split(",")
            .map((f) => f.trim())
            .filter(Boolean)
        : [],
    );

    // Fetch form fields
    setIsLoadingFields(true);
    try {
      const fields = await fetchFormFields(form.asset_uid);
      setFormFields(fields || []);
    } catch (err) {
      setMappingStatus({
        type: "error",
        message: err.response?.data?.detail || "Failed to fetch form fields.",
      });
      setFormFields([]);
    } finally {
      setIsLoadingFields(false);
    }
  }

  async function handleSaveMapping() {
    if (!configForm) return;

    setIsSavingMapping(true);
    setMappingStatus(null);
    try {
      await updateForm(configForm.asset_uid, {
        polygon_field: polygonFields.join(","),
        region_field: regionFields.join(",") || null,
        sub_region_field: subRegionFields.join(",") || null,
        plot_name_field: plotNameFields.join(","),
      });
      setMappingStatus({
        type: "success",
        message: "Field mappings saved successfully.",
      });
      setTimeout(() => {
        setConfigDialogOpen(false);
      }, 1500);
    } catch (err) {
      setMappingStatus({
        type: "error",
        message: err.response?.data?.detail || "Failed to save field mappings.",
      });
    } finally {
      setIsSavingMapping(false);
    }
  }

  function togglePolygonField(fullPath) {
    setPolygonFields((prev) =>
      prev.includes(fullPath)
        ? prev.filter((f) => f !== fullPath)
        : [...prev, fullPath],
    );
  }

  function togglePlotNameField(fullPath) {
    setPlotNameFields((prev) =>
      prev.includes(fullPath)
        ? prev.filter((f) => f !== fullPath)
        : [...prev, fullPath],
    );
  }

  function toggleRegionField(fullPath) {
    setRegionFields((prev) =>
      prev.includes(fullPath)
        ? prev.filter((f) => f !== fullPath)
        : [...prev, fullPath],
    );
  }

  function toggleSubRegionField(fullPath) {
    setSubRegionFields((prev) =>
      prev.includes(fullPath)
        ? prev.filter((f) => f !== fullPath)
        : [...prev, fullPath],
    );
  }

  // Sort fields: geoshape/geotrace first for polygon selector
  const sortedFieldsForPolygon = [...formFields].sort((a, b) => {
    const aIsGeo = a.type === "geoshape" || a.type === "geotrace";
    const bIsGeo = b.type === "geoshape" || b.type === "geotrace";
    if (aIsGeo && !bIsGeo) return -1;
    if (!aIsGeo && bIsGeo) return 1;
    return 0;
  });

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
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleConfigureClick(form)}
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

      {/* Field Mapping Configuration Dialog */}
      <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Configure Field Mappings — {configForm?.name}
            </DialogTitle>
            <DialogDescription>
              Map form fields to plot attributes for automatic plot creation and
              updates
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {isLoadingFields ? (
              <div className="space-y-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : formFields.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-6">
                No fields found for this form.
              </p>
            ) : (
              <>
                {/* Polygon field(s) - Multi-select */}
                <div className="space-y-2">
                  <Label>Polygon field(s)</Label>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="outline"
                        className="w-full justify-between h-auto min-h-[2.25rem] px-3 py-2"
                      >
                        <div className="flex flex-wrap gap-1">
                          {polygonFields.length === 0 ? (
                            <span className="text-muted-foreground">
                              Select polygon fields...
                            </span>
                          ) : (
                            polygonFields.map((fullPath) => {
                              const field = formFields.find(
                                (f) => f.full_path === fullPath,
                              );
                              return (
                                <Badge key={fullPath} variant="secondary">
                                  {field?.label || fullPath}
                                </Badge>
                              );
                            })
                          )}
                        </div>
                        <ChevronDown className="size-4 opacity-50 shrink-0" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent className="w-[--radix-dropdown-menu-trigger-width]">
                      {sortedFieldsForPolygon.map((field) => (
                        <DropdownMenuCheckboxItem
                          key={field.full_path}
                          checked={polygonFields.includes(field.full_path)}
                          onCheckedChange={() =>
                            togglePolygonField(field.full_path)
                          }
                        >
                          {field.label} ({field.type})
                        </DropdownMenuCheckboxItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <p className="text-xs text-muted-foreground">
                    Geo fields (geoshape/geotrace) are shown first
                  </p>
                </div>

                {/* Region field(s) - Multi-select */}
                <div className="space-y-2">
                  <Label>Region field(s)</Label>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="outline"
                        className="w-full justify-between h-auto min-h-[2.25rem] px-3 py-2"
                      >
                        <div className="flex flex-wrap gap-1">
                          {regionFields.length === 0 ? (
                            <span className="text-muted-foreground">
                              Select region fields...
                            </span>
                          ) : (
                            regionFields.map((fullPath) => {
                              const field = formFields.find(
                                (f) => f.full_path === fullPath,
                              );
                              return (
                                <Badge key={fullPath} variant="secondary">
                                  {field?.label || fullPath}
                                </Badge>
                              );
                            })
                          )}
                        </div>
                        <ChevronDown className="size-4 opacity-50 shrink-0" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent className="w-[--radix-dropdown-menu-trigger-width]">
                      {formFields.map((field) => (
                        <DropdownMenuCheckboxItem
                          key={field.full_path}
                          checked={regionFields.includes(field.full_path)}
                          onCheckedChange={() =>
                            toggleRegionField(field.full_path)
                          }
                        >
                          {field.label} ({field.type})
                        </DropdownMenuCheckboxItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <p className="text-xs text-muted-foreground">
                    Multiple fields will be joined with &quot; - &quot;
                  </p>
                </div>

                {/* Sub-region field(s) - Multi-select */}
                <div className="space-y-2">
                  <Label>Sub-region field(s)</Label>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="outline"
                        className="w-full justify-between h-auto min-h-[2.25rem] px-3 py-2"
                      >
                        <div className="flex flex-wrap gap-1">
                          {subRegionFields.length === 0 ? (
                            <span className="text-muted-foreground">
                              Select sub-region fields...
                            </span>
                          ) : (
                            subRegionFields.map((fullPath) => {
                              const field = formFields.find(
                                (f) => f.full_path === fullPath,
                              );
                              return (
                                <Badge key={fullPath} variant="secondary">
                                  {field?.label || fullPath}
                                </Badge>
                              );
                            })
                          )}
                        </div>
                        <ChevronDown className="size-4 opacity-50 shrink-0" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent className="w-[--radix-dropdown-menu-trigger-width]">
                      {formFields.map((field) => (
                        <DropdownMenuCheckboxItem
                          key={field.full_path}
                          checked={subRegionFields.includes(field.full_path)}
                          onCheckedChange={() =>
                            toggleSubRegionField(field.full_path)
                          }
                        >
                          {field.label} ({field.type})
                        </DropdownMenuCheckboxItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <p className="text-xs text-muted-foreground">
                    Multiple fields will be joined with &quot; - &quot;
                  </p>
                </div>

                {/* Plot name field(s) - Multi-select */}
                <div className="space-y-2">
                  <Label>Plot name field(s)</Label>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="outline"
                        className="w-full justify-between h-auto min-h-[2.25rem] px-3 py-2"
                      >
                        <div className="flex flex-wrap gap-1">
                          {plotNameFields.length === 0 ? (
                            <span className="text-muted-foreground">
                              Select plot name fields...
                            </span>
                          ) : (
                            plotNameFields.map((fullPath) => {
                              const field = formFields.find(
                                (f) => f.full_path === fullPath,
                              );
                              return (
                                <Badge key={fullPath} variant="secondary">
                                  {field?.label || fullPath}
                                </Badge>
                              );
                            })
                          )}
                        </div>
                        <ChevronDown className="size-4 opacity-50 shrink-0" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent className="w-[--radix-dropdown-menu-trigger-width]">
                      {formFields.map((field) => (
                        <DropdownMenuCheckboxItem
                          key={field.full_path}
                          checked={plotNameFields.includes(field.full_path)}
                          onCheckedChange={() =>
                            togglePlotNameField(field.full_path)
                          }
                        >
                          {field.label} ({field.type})
                        </DropdownMenuCheckboxItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <p className="text-xs text-muted-foreground">
                    Multiple fields will be joined with spaces
                  </p>
                </div>
              </>
            )}

            {mappingStatus && (
              <div
                role="alert"
                className={`rounded-md p-3 text-sm ${
                  mappingStatus.type === "success"
                    ? "bg-status-approved/10 text-status-approved"
                    : "bg-destructive/10 text-destructive"
                }`}
              >
                {mappingStatus.message}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfigDialogOpen(false)}
              disabled={isSavingMapping}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveMapping}
              disabled={isSavingMapping || isLoadingFields}
            >
              {isSavingMapping ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Mappings"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
