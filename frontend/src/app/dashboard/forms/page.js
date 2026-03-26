"use client";

import { useState } from "react";
import { logout } from "@/app/actions/auth";
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
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Plus, Loader2, RefreshCw, Settings, ChevronDown } from "lucide-react";
import api from "@/lib/api";

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
  const [filterSelectFields, setFilterSelectFields] = useState([]);
  const [isLoadingFields, setIsLoadingFields] = useState(false);
  const [isSavingMapping, setIsSavingMapping] = useState(false);
  const [mappingStatus, setMappingStatus] = useState(null);

  // Field mapping values (Plot Structure tab)
  const [polygonFields, setPolygonFields] = useState([]);
  const [regionFields, setRegionFields] = useState([]);
  const [subRegionFields, setSubRegionFields] = useState([]);
  const [plotNameFields, setPlotNameFields] = useState([]);
  const [filterFields, setFilterFields] = useState([]);
  const [sortableFields, setSortableFields] = useState([]);

  // Detail Fields tab state
  const [configTab, setConfigTab] = useState("structure");
  const [fieldSettings, setFieldSettings] = useState([]);
  const [formQuestions, setFormQuestions] = useState([]);
  const [detailMappings, setDetailMappings] = useState({});
  const [isLoadingDetailFields, setIsLoadingDetailFields] = useState(false);

  // Farmer Fields tab state
  const [farmerUniqueFields, setFarmerUniqueFields] = useState([]);
  const [farmerValuesFields, setFarmerValuesFields] = useState([]);
  const [isLoadingFarmerMapping, setIsLoadingFarmerMapping] = useState(false);

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
      const isKoboAuth = err.response?.data?.error_type === "kobo_unauthorized";
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

  async function handleConfigureClick(form) {
    setConfigForm(form);
    setConfigDialogOpen(true);
    setMappingStatus(null);
    setConfigTab("structure");

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
    setFilterFields(
      Array.isArray(form.filter_fields) ? form.filter_fields : [],
    );
    setSortableFields(
      Array.isArray(form.sortable_fields) ? form.sortable_fields : [],
    );

    // Fetch all fields and filter-eligible fields in parallel
    setIsLoadingFields(true);
    try {
      const [allFields, filterFields_] = await Promise.all([
        fetchFormFields(form.asset_uid),
        fetchFormFields(form.asset_uid, { is_filter: true }),
      ]);
      setFormFields(allFields || []);
      const selects = (filterFields_ || []).filter(
        (f) => f.type === "select_one" || f.type === "select_multiple",
      );
      setFilterSelectFields(selects);
    } catch (err) {
      setMappingStatus({
        type: "error",
        message: err.response?.data?.detail || "Failed to fetch form fields.",
      });
      setFormFields([]);
      setFilterSelectFields([]);
    } finally {
      setIsLoadingFields(false);
    }

    // Fetch field settings, form questions, detail mappings, and farmer field mapping
    setIsLoadingDetailFields(true);
    setIsLoadingFarmerMapping(true);
    try {
      const [settingsRes, questionsRes, mappingsRes, farmerRes] =
        await Promise.all([
          api.get("/v1/odk/field-settings/"),
          api.get(`/v1/odk/forms/${form.asset_uid}/form_questions/`),
          api.get(`/v1/odk/field-mappings/?form_id=${form.asset_uid}`),
          api.get(`/v1/odk/forms/${form.asset_uid}/farmer-field-mapping/`),
        ]);
      setFieldSettings(settingsRes.data?.results || settingsRes.data || []);
      setFormQuestions(questionsRes.data || []);
      // Convert mappings array to { field_name: form_question_id }
      const mappingsMap = {};
      const mappingsData = mappingsRes.data?.results || mappingsRes.data || [];
      for (const m of mappingsData) {
        mappingsMap[m.field_name] = String(m.form_question_id);
      }
      setDetailMappings(mappingsMap);
      setFarmerUniqueFields(farmerRes.data?.unique_fields || []);
      setFarmerValuesFields(farmerRes.data?.values_fields || []);
    } catch {
      setFieldSettings([]);
      setFormQuestions([]);
      setDetailMappings({});
      setFarmerUniqueFields([]);
      setFarmerValuesFields([]);
    } finally {
      setIsLoadingDetailFields(false);
      setIsLoadingFarmerMapping(false);
    }
  }

  async function handleSaveMapping() {
    if (!configForm) return;

    setIsSavingMapping(true);
    setMappingStatus(null);
    try {
      // Save Plot Structure fields
      await updateForm(configForm.asset_uid, {
        polygon_field: polygonFields.join(","),
        region_field: regionFields.join(",") || null,
        sub_region_field: subRegionFields.join(",") || null,
        plot_name_field: plotNameFields.join(","),
        filter_fields: filterFields.length > 0 ? filterFields : null,
        sortable_fields: sortableFields.length > 0 ? sortableFields : null,
      });

      // Save Detail Fields mappings
      // Convert { field_name: "question_id" } to { field_name: int|null }
      const detailPayload = {};
      for (const fs of fieldSettings) {
        const qId = detailMappings[fs.name];
        detailPayload[fs.name] = qId ? parseInt(qId, 10) : null;
      }
      await api.put(
        `/v1/odk/field-mappings/${configForm.asset_uid}/`,
        detailPayload,
      );

      // Save Farmer Field Mapping
      if (farmerUniqueFields.length > 0) {
        await api.put(
          `/v1/odk/forms/${configForm.asset_uid}/farmer-field-mapping/`,
          {
            unique_fields: farmerUniqueFields,
            values_fields:
              farmerValuesFields.length > 0
                ? farmerValuesFields
                : farmerUniqueFields,
          },
        );
      }

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

  function toggleFilterField(name) {
    setFilterFields((prev) =>
      prev.includes(name) ? prev.filter((f) => f !== name) : [...prev, name],
    );
  }

  function toggleSortableField(name) {
    setSortableFields((prev) =>
      prev.includes(name) ? prev.filter((f) => f !== name) : [...prev, name],
    );
  }

  function toggleFarmerUniqueField(name) {
    setFarmerUniqueFields((prev) =>
      prev.includes(name) ? prev.filter((f) => f !== name) : [...prev, name],
    );
  }

  function toggleFarmerValuesField(name) {
    setFarmerValuesFields((prev) =>
      prev.includes(name) ? prev.filter((f) => f !== name) : [...prev, name],
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
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-x-hidden overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Configure Field Mappings — {configForm?.name}
            </DialogTitle>
            <DialogDescription>
              Map form fields to plot attributes for automatic plot creation and
              updates
            </DialogDescription>
          </DialogHeader>

          <Tabs
            value={configTab}
            onValueChange={setConfigTab}
            className="min-w-0 overflow-hidden py-4"
          >
            <TabsList className="w-full">
              <TabsTrigger value="structure">Plot Structure</TabsTrigger>
              <TabsTrigger value="detail-fields">Detail Fields</TabsTrigger>
              <TabsTrigger value="farmer-fields">Farmer Fields</TabsTrigger>
            </TabsList>

            <TabsContent value="structure">
              <p className="mb-4 text-xs text-muted-foreground">
                Define how raw submissions are converted into plots — geometry
                source, location hierarchy, naming, and available filters.
              </p>
              <div className="space-y-6">
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
                              checked={subRegionFields.includes(
                                field.full_path,
                              )}
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

                    {/* Filter fields - select_one/select_multiple only */}
                    {filterSelectFields.length > 0 && (
                      <div className="space-y-2">
                        <Label>Additional Filter fields</Label>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="outline"
                              className="w-full justify-between h-auto min-h-[2.25rem] px-3 py-2"
                            >
                              <div className="flex flex-wrap gap-1">
                                {filterFields.length === 0 ? (
                                  <span className="text-muted-foreground">
                                    Select filter fields...
                                  </span>
                                ) : (
                                  filterFields.map((name) => {
                                    const field = formFields.find(
                                      (f) =>
                                        f.name === name || f.full_path === name,
                                    );
                                    return (
                                      <Badge key={name} variant="secondary">
                                        {field?.label || name}
                                      </Badge>
                                    );
                                  })
                                )}
                              </div>
                              <ChevronDown className="size-4 opacity-50 shrink-0" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent className="w-[--radix-dropdown-menu-trigger-width]">
                            {filterSelectFields.map((field) => (
                              <DropdownMenuCheckboxItem
                                key={field.name}
                                checked={filterFields.includes(field.name)}
                                onCheckedChange={() =>
                                  toggleFilterField(field.name)
                                }
                              >
                                {field.label} ({field.type})
                              </DropdownMenuCheckboxItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                        <p className="text-xs text-muted-foreground">
                          Additional fields to filter by in the plot list view.
                          These will be added as separate filters alongside the
                          region/sub-region filters, so best to choose fields
                          with a limited number of options (e.g. select_one or
                          select_multiple fields).
                        </p>
                      </div>
                    )}

                    {/* Sortable fields - any question type */}
                    {formFields.length > 0 && (
                      <div className="space-y-2">
                        <Label>Sortable fields</Label>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="outline"
                              className="w-full justify-between h-auto min-h-[2.25rem] px-3 py-2"
                            >
                              <div className="flex flex-wrap gap-1">
                                {sortableFields.length === 0 ? (
                                  <span className="text-muted-foreground">
                                    Select sortable fields...
                                  </span>
                                ) : (
                                  sortableFields.map((name) => {
                                    const field = formFields.find(
                                      (f) =>
                                        f.name === name || f.full_path === name,
                                    );
                                    return (
                                      <Badge key={name} variant="secondary">
                                        {field?.label || name}
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
                                key={field.name}
                                checked={sortableFields.includes(field.name)}
                                onCheckedChange={() =>
                                  toggleSortableField(field.name)
                                }
                              >
                                {field.label} ({field.type})
                              </DropdownMenuCheckboxItem>
                            ))}
                          </DropdownMenuContent>
                        </DropdownMenu>
                        <p className="text-xs text-muted-foreground">
                          Fields that can be sorted in the submissions table.
                          Columns with sorting enabled will show sort arrows in
                          the table header.
                        </p>
                      </div>
                    )}
                  </>
                )}
              </div>
            </TabsContent>

            <TabsContent value="detail-fields">
              <p className="mb-4 text-xs text-muted-foreground">
                Map form questions to standardized display fields shown in the
                plot detail panel.
              </p>
              <div className="space-y-4">
                {isLoadingDetailFields || isLoadingFields ? (
                  <div className="space-y-3">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Skeleton key={i} className="h-10 w-full" />
                    ))}
                  </div>
                ) : fieldSettings.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-6">
                    No field settings available. Run the seed command first.
                  </p>
                ) : (
                  fieldSettings.map((fs) => {
                    const selectedId = detailMappings[fs.name];
                    const selectedQ = selectedId
                      ? formQuestions.find((q) => String(q.id) === selectedId)
                      : null;
                    return (
                      <div key={fs.id} className="flex flex-col gap-1.5">
                        <Label className="text-sm capitalize">
                          {fs.name.replace(/_/g, " ")}
                        </Label>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="outline"
                              className="w-full min-w-0 justify-between h-auto min-h-[2.25rem] px-3 py-2"
                            >
                              <span className="min-w-0 truncate text-left">
                                {selectedQ
                                  ? `${selectedQ.label} (${selectedQ.name})`
                                  : "Select question..."}
                              </span>
                              <ChevronDown className="size-4 opacity-50 shrink-0" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent className="w-[--radix-dropdown-menu-trigger-width] max-h-64 overflow-y-auto">
                            <DropdownMenuRadioGroup
                              value={selectedId || "none"}
                              onValueChange={(val) =>
                                setDetailMappings((prev) => ({
                                  ...prev,
                                  [fs.name]: val === "none" ? undefined : val,
                                }))
                              }
                            >
                              <DropdownMenuRadioItem value="none">
                                None
                              </DropdownMenuRadioItem>
                              {formQuestions.map((q) => (
                                <DropdownMenuRadioItem
                                  key={q.id}
                                  value={String(q.id)}
                                >
                                  {q.label} ({q.name})
                                </DropdownMenuRadioItem>
                              ))}
                            </DropdownMenuRadioGroup>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    );
                  })
                )}
              </div>
            </TabsContent>

            <TabsContent value="farmer-fields">
              <p className="mb-4 text-xs text-muted-foreground">
                Define which form fields identify unique farmers and which
                values to store. These are used during sync to deduplicate
                farmers and populate the Farmer table in XLSX exports.
              </p>
              <div className="space-y-6">
                {isLoadingFarmerMapping || isLoadingFields ? (
                  <div className="space-y-4">
                    <Skeleton className="h-10 w-full" />
                    <Skeleton className="h-10 w-full" />
                  </div>
                ) : formFields.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-6">
                    No fields found. Sync the form first to populate questions.
                  </p>
                ) : (
                  <>
                    {/* Unique fields - used for farmer deduplication */}
                    <div className="space-y-2">
                      <Label>Unique fields (identity)</Label>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="outline"
                            className="w-full justify-between h-auto min-h-[2.25rem] px-3 py-2"
                          >
                            <div className="flex flex-wrap gap-1">
                              {farmerUniqueFields.length === 0 ? (
                                <span className="text-muted-foreground">
                                  Select unique fields...
                                </span>
                              ) : (
                                farmerUniqueFields.map((name) => {
                                  const field = formFields.find(
                                    (f) =>
                                      f.name === name || f.full_path === name,
                                  );
                                  return (
                                    <Badge key={name} variant="secondary">
                                      {field?.label || name}
                                    </Badge>
                                  );
                                })
                              )}
                            </div>
                            <ChevronDown className="size-4 opacity-50 shrink-0" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent className="w-[--radix-dropdown-menu-trigger-width] max-h-64 overflow-y-auto">
                          {formFields.map((field) => (
                            <DropdownMenuCheckboxItem
                              key={field.name}
                              checked={farmerUniqueFields.includes(field.name)}
                              onCheckedChange={() =>
                                toggleFarmerUniqueField(field.name)
                              }
                            >
                              {field.label} ({field.type})
                            </DropdownMenuCheckboxItem>
                          ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                      <p className="text-xs text-muted-foreground">
                        Fields that uniquely identify a farmer (e.g. First Name
                        + Father&apos;s Name + Grandfather&apos;s Name). Values
                        are joined with &quot; - &quot; for deduplication.
                      </p>
                    </div>

                    {/* Values fields - stored in farmer record */}
                    <div className="space-y-2">
                      <Label>Values fields (data to store)</Label>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="outline"
                            className="w-full justify-between h-auto min-h-[2.25rem] px-3 py-2"
                          >
                            <div className="flex flex-wrap gap-1">
                              {farmerValuesFields.length === 0 ? (
                                <span className="text-muted-foreground">
                                  Select values fields...
                                </span>
                              ) : (
                                farmerValuesFields.map((name) => {
                                  const field = formFields.find(
                                    (f) =>
                                      f.name === name || f.full_path === name,
                                  );
                                  return (
                                    <Badge key={name} variant="secondary">
                                      {field?.label || name}
                                    </Badge>
                                  );
                                })
                              )}
                            </div>
                            <ChevronDown className="size-4 opacity-50 shrink-0" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent className="w-[--radix-dropdown-menu-trigger-width] max-h-64 overflow-y-auto">
                          {formFields.map((field) => (
                            <DropdownMenuCheckboxItem
                              key={field.name}
                              checked={farmerValuesFields.includes(field.name)}
                              onCheckedChange={() =>
                                toggleFarmerValuesField(field.name)
                              }
                            >
                              {field.label} ({field.type})
                            </DropdownMenuCheckboxItem>
                          ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                      <p className="text-xs text-muted-foreground">
                        Fields to store as key-value pairs on the farmer record.
                        If empty, defaults to the unique fields above.
                      </p>
                    </div>
                  </>
                )}
              </div>
            </TabsContent>

            {mappingStatus && (
              <div
                role="alert"
                className={`mt-4 rounded-md p-3 text-sm ${
                  mappingStatus.type === "success"
                    ? "bg-status-approved/10 text-status-approved"
                    : "bg-destructive/10 text-destructive"
                }`}
              >
                {mappingStatus.message}
              </div>
            )}
          </Tabs>

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
