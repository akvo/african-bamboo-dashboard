"use client";

import { useEffect, useMemo, useState } from "react";
import {
  EXCLUDED_QUESTION_TYPES,
  EXCLUDED_QUESTION_NAMES,
} from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
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
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, ChevronDown } from "lucide-react";
import { MultiSelectDropdown } from "@/components/multi-select-dropdown";
import api from "@/lib/api";

function parseCommaSeparated(value) {
  return value
    ? value
        .split(",")
        .map((f) => f.trim())
        .filter(Boolean)
    : [];
}

function useToggleList(initial) {
  const [list, setList] = useState(initial);
  const toggle = (item) =>
    setList((prev) =>
      prev.includes(item)
        ? prev.filter((f) => f !== item)
        : [...prev, item],
    );
  return [list, setList, toggle];
}

export function FieldMappingDialog({
  open,
  onOpenChange,
  form,
  fetchFormFields,
  updateForm,
}) {
  const [configTab, setConfigTab] = useState("structure");
  const [formFields, setFormFields] = useState([]);
  const [isLoadingFields, setIsLoadingFields] = useState(false);
  const [isSavingMapping, setIsSavingMapping] = useState(false);
  const [mappingStatus, setMappingStatus] = useState(null);

  // Plot Structure tab
  const [polygonFields, setPolygonFields, togglePolygonField] =
    useToggleList([]);
  const [regionFields, setRegionFields, toggleRegionField] =
    useToggleList([]);
  const [subRegionFields, setSubRegionFields, toggleSubRegionField] =
    useToggleList([]);
  const [plotNameFields, setPlotNameFields] = useToggleList([]);
  const [sortableFields, setSortableFields, toggleSortableField] =
    useToggleList([]);

  // Detail Fields tab
  const [fieldSettings, setFieldSettings] = useState([]);
  const [formQuestions, setFormQuestions] = useState([]);
  const [detailMappings, setDetailMappings] = useState({});
  const [isLoadingDetailFields, setIsLoadingDetailFields] = useState(false);

  // Farmer Fields tab
  const [farmerUniqueFields, setFarmerUniqueFields, toggleFarmerUniqueField] =
    useToggleList([]);
  const [farmerValuesFields, setFarmerValuesFields, toggleFarmerValuesField] =
    useToggleList([]);
  const [farmerUidStart, setFarmerUidStart] = useState(1);
  const [isLoadingFarmerMapping, setIsLoadingFarmerMapping] = useState(false);

  // Load data when dialog opens with a form
  useEffect(() => {
    if (!open || !form) {
      return;
    }

    setMappingStatus(null);
    setConfigTab("structure");

    // Pre-populate existing values
    setPolygonFields(parseCommaSeparated(form.polygon_field));
    setRegionFields(parseCommaSeparated(form.region_field));
    setSubRegionFields(parseCommaSeparated(form.sub_region_field));
    setPlotNameFields(parseCommaSeparated(form.plot_name_field));
    setSortableFields(
      Array.isArray(form.sortable_fields) ? form.sortable_fields : [],
    );

    // Fetch all fields
    setIsLoadingFields(true);
    fetchFormFields(form.asset_uid)
      .then((allFields) => setFormFields(allFields || []))
      .catch((err) => {
        setMappingStatus({
          type: "error",
          message:
            err.response?.data?.detail || "Failed to fetch form fields.",
        });
        setFormFields([]);
      })
      .finally(() => setIsLoadingFields(false));

    // Fetch field settings, form questions, detail mappings, and farmer mapping
    setIsLoadingDetailFields(true);
    setIsLoadingFarmerMapping(true);
    Promise.all([
      api.get("/v1/odk/field-settings/"),
      api.get(`/v1/odk/forms/${form.asset_uid}/form_questions/`),
      api.get(`/v1/odk/field-mappings/?form_id=${form.asset_uid}`),
      api.get(`/v1/odk/forms/${form.asset_uid}/farmer-field-mapping/`),
    ])
      .then(([settingsRes, questionsRes, mappingsRes, farmerRes]) => {
        setFieldSettings(
          settingsRes.data?.results || settingsRes.data || [],
        );
        setFormQuestions(questionsRes.data || []);
        const mappingsMap = {};
        const mappingsData =
          mappingsRes.data?.results || mappingsRes.data || [];
        for (const m of mappingsData) {
          mappingsMap[m.field_name] = String(m.form_question_id);
        }
        setDetailMappings(mappingsMap);
        setFarmerUniqueFields(farmerRes.data?.unique_fields || []);
        setFarmerValuesFields(farmerRes.data?.values_fields || []);
        setFarmerUidStart(farmerRes.data?.uid_start || 1);
      })
      .catch(() => {
        setFieldSettings([]);
        setFormQuestions([]);
        setDetailMappings({});
        setFarmerUniqueFields([]);
        setFarmerValuesFields([]);
        setFarmerUidStart(1);
      })
      .finally(() => {
        setIsLoadingDetailFields(false);
        setIsLoadingFarmerMapping(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, form?.asset_uid]);

  async function handleSaveMapping() {
    if (!form) {
      return;
    }

    setIsSavingMapping(true);
    setMappingStatus(null);
    try {
      await updateForm(form.asset_uid, {
        polygon_field: polygonFields.join(","),
        region_field: regionFields.join(",") || null,
        sub_region_field: subRegionFields.join(",") || null,
        plot_name_field: plotNameFields.join(","),
        sortable_fields: sortableFields.length > 0 ? sortableFields : null,
      });

      const detailPayload = {};
      for (const fs of fieldSettings) {
        const qId = detailMappings[fs.name];
        detailPayload[fs.name] = qId ? parseInt(qId, 10) : null;
      }
      await api.put(
        `/v1/odk/field-mappings/${form.asset_uid}/`,
        detailPayload,
      );

      if (farmerUniqueFields.length > 0) {
        await api.put(
          `/v1/odk/forms/${form.asset_uid}/farmer-field-mapping/`,
          {
            unique_fields: farmerUniqueFields,
            values_fields:
              farmerValuesFields.length > 0
                ? farmerValuesFields
                : farmerUniqueFields,
            uid_start: farmerUidStart,
          },
        );
      }

      setMappingStatus({
        type: "success",
        message: "Field mappings saved successfully.",
      });
      setTimeout(() => onOpenChange(false), 1500);
    } catch (err) {
      setMappingStatus({
        type: "error",
        message:
          err.response?.data?.detail || "Failed to save field mappings.",
      });
    } finally {
      setIsSavingMapping(false);
    }
  }

  const sortableEligibleFields = useMemo(() => {
    const mapped = new Set([...regionFields, ...subRegionFields]);
    return formFields.filter(
      (f) =>
        !mapped.has(f.name) &&
        !EXCLUDED_QUESTION_TYPES.includes(f.type) &&
        !EXCLUDED_QUESTION_NAMES.includes(f.name) &&
        !f.name.startsWith("validate_"),
    );
  }, [formFields, regionFields, subRegionFields]);

  const sortedFieldsForPolygon = useMemo(
    () =>
      [...formFields].sort((a, b) => {
        const aIsGeo = a.type === "geoshape" || a.type === "geotrace";
        const bIsGeo = b.type === "geoshape" || b.type === "geotrace";
        if (aIsGeo && !bIsGeo) {
          return -1;
        }
        if (!aIsGeo && bIsGeo) {
          return 1;
        }
        return 0;
      }),
    [formFields],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-x-hidden overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            Configure Field Mappings — {form?.name}
          </DialogTitle>
          <DialogDescription>
            Map form fields to plot attributes for automatic plot creation
            and updates
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

          {/* Plot Structure Tab */}
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
                  <MultiSelectDropdown
                    label="Polygon field(s)"
                    placeholder="Select polygon fields..."
                    hint="Geo fields (geoshape/geotrace) are shown first"
                    items={sortedFieldsForPolygon}
                    selected={polygonFields}
                    onToggle={togglePolygonField}
                    getItemKey={(item) => item.full_path}
                  />

                  <MultiSelectDropdown
                    label="Region field(s)"
                    placeholder="Select region fields..."
                    hint='Multiple fields will be joined with " - "'
                    items={formFields}
                    selected={regionFields}
                    onToggle={toggleRegionField}
                    getItemKey={(item) => item.full_path}
                  />

                  <MultiSelectDropdown
                    label="Sub-region field(s)"
                    placeholder="Select sub-region fields..."
                    hint='Multiple fields will be joined with " - "'
                    items={formFields}
                    selected={subRegionFields}
                    onToggle={toggleSubRegionField}
                    getItemKey={(item) => item.full_path}
                  />

                  {sortableEligibleFields.length > 0 && (
                    <MultiSelectDropdown
                      label="Sortable fields"
                      placeholder="Select sortable fields..."
                      hint="Only fields visible as columns in the submissions table are listed. Columns with sorting enabled will show sort arrows in the table header."
                      items={sortableEligibleFields}
                      selected={sortableFields}
                      onToggle={toggleSortableField}
                      getItemKey={(item) => item.name}
                    />
                  )}
                </>
              )}
            </div>
          </TabsContent>

          {/* Detail Fields Tab */}
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
                    ? formQuestions.find(
                        (q) => String(q.id) === selectedId,
                      )
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
                                [fs.name]:
                                  val === "none" ? undefined : val,
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

          {/* Farmer Fields Tab */}
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
                  No fields found. Sync the form first to populate
                  questions.
                </p>
              ) : (
                <>
                  <MultiSelectDropdown
                    label="Unique fields (identity)"
                    placeholder="Select unique fields..."
                    hint='Fields that uniquely identify a farmer (e.g. First Name + Father&apos;s Name + Grandfather&apos;s Name). Values are joined with " - " for deduplication.'
                    items={formFields}
                    selected={farmerUniqueFields}
                    onToggle={toggleFarmerUniqueField}
                    getItemKey={(item) => item.name}
                    scrollable
                  />

                  <MultiSelectDropdown
                    label="Values fields (data to store)"
                    placeholder="Select values fields..."
                    hint="Fields to store as key-value pairs on the farmer record. If empty, defaults to the unique fields above."
                    items={formFields}
                    selected={farmerValuesFields}
                    onToggle={toggleFarmerValuesField}
                    getItemKey={(item) => item.name}
                    scrollable
                  />

                  <div className="space-y-2">
                    <Label htmlFor="uid-start">
                      Starting Farmer ID Number
                    </Label>
                    <Input
                      id="uid-start"
                      type="number"
                      min={1}
                      value={farmerUidStart}
                      onChange={(e) =>
                        setFarmerUidStart(
                          Math.max(
                            1,
                            parseInt(e.target.value, 10) || 1,
                          ),
                        )
                      }
                      className="w-40"
                      placeholder="1"
                    />
                    <p className="text-xs text-muted-foreground">
                      Minimum starting number for new farmer IDs. Use this
                      to continue from legacy data (e.g., enter 351 to
                      start after AB00350). Only affects new farmers.
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
            onClick={() => onOpenChange(false)}
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
  );
}
