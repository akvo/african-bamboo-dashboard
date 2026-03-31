"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Map,
  User,
  ArrowRight,
  SquarePen,
  ImageIcon,
  MapPin,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getPlotStatus } from "@/lib/plot-utils";
import { extractPlotDetails } from "@/lib/field-mapping";
import api from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import PlotHeaderCard from "@/components/map/plot-header-card";
import AttachmentCard from "@/components/map/attachment-card";
import EditableField from "@/components/map/editable-field";
import { PREFIX_FARM_ID } from "@/lib/constants";
import { useMapState } from "@/hooks/useMapState";

const SECTION_FIELD_MAP = {
  enumerator: ["enumerator"],
  farmer: ["farmer", "father_name", "grandfather_name"],
};

function SectionHeader({
  icon: Icon,
  title,
  isEditing,
  onEdit,
  onSave,
  onCancel,
  isSaving,
}) {
  return (
    <div className="w-full flex items-center justify-between">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        {Icon && <Icon className="size-4" />}
        <span>{title}</span>
      </div>
      {isEditing ? (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="text-sm text-muted-foreground hover:text-foreground cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={isSaving}
            className="text-sm text-primary hover:text-primary/80 cursor-pointer font-medium disabled:opacity-50"
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
        </div>
      ) : onEdit ? (
        <button
          type="button"
          onClick={onEdit}
          className="ml-2 text-muted-foreground hover:text-foreground items-center gap-1 cursor-pointer text-sm"
        >
          Edit
        </button>
      ) : null}
    </div>
  );
}

function DataField({ label, value }) {
  if (!value) return null;
  return (
    <div className="flex flex-1 flex-col gap-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm text-foreground">{value}</span>
    </div>
  );
}

function DataFieldRow({ fields }) {
  const visibleFields = fields.filter((f) => f.value);
  if (visibleFields.length === 0) return null;
  return (
    <div
      className={cn("flex items-start", "divide-x divide-muted-foreground/20")}
    >
      {visibleFields.map((field, i) => (
        <div key={field.label} className={cn(i > 0 && "pl-3", "flex-1")}>
          <DataField label={field.label} value={field.value} />
        </div>
      ))}
    </div>
  );
}

function PersonSection({
  icon: Icon,
  title,
  name,
  subTitle = null,
  fields = [],
  children,
  isEditing,
  onEdit,
  onSave,
  onCancel,
  isSaving,
}) {
  if (!name && !isEditing) return null;
  const visibleFields = fields.filter((f) => f.value);
  return (
    <div className="flex flex-col gap-3 rounded-md border border-card-foreground/10 p-3 bg-card">
      <SectionHeader
        icon={Icon}
        title={title}
        isEditing={isEditing}
        onEdit={onEdit}
        onSave={onSave}
        onCancel={onCancel}
        isSaving={isSaving}
      />
      <Separator className="bg-muted-foreground/20" />
      {!isEditing && name && (
        <p className="text-sm font-bold text-foreground">{name}</p>
      )}
      {!isEditing && subTitle && (
        <p className="text-sm text-muted-foreground">{subTitle}</p>
      )}
      {!isEditing && visibleFields.length > 0 && (
        <DataFieldRow fields={visibleFields} />
      )}
      {children}
    </div>
  );
}

function TimelineRow({ label, value }) {
  return (
    <div className="flex items-center justify-between border-b border-card-foreground/10 py-3 last:border-b-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm text-foreground">{value}</span>
    </div>
  );
}

export default function PlotDetailPanel({
  plot,
  isLoading = false,
  onBack,
  onApprove,
  onReject,
  onRevertToPending,
  onStartEditing,
  onOpenTitleDeed,
}) {
  const [submission, setSubmission] = useState(null);
  const [isLoadingSub, setIsLoadingSub] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [activeTab, setActiveTab] = useState("details");

  // Edit mode state
  const [editingSection, setEditingSection] = useState(null);
  const [editValues, setEditValues] = useState({});
  const [isSaving, setIsSaving] = useState(false);
  const [formQuestions, setFormQuestions] = useState([]);

  const mapState = useMapState();

  useEffect(() => {
    if (!plot?.submission_uuid) {
      setSubmission(null);
      return;
    }
    let cancelled = false;
    setIsLoadingSub(true);
    api
      .get(`/v1/odk/submissions/${plot.submission_uuid}/`)
      .then((res) => {
        if (!cancelled) {
          setSubmission(res.data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSubmission(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoadingSub(false);
      });
    return () => {
      cancelled = true;
    };
  }, [plot?.submission_uuid]);

  // Reset edit state when plot changes
  useEffect(() => {
    setEditingSection(null);
    setEditValues({});
  }, [plot?.submission_uuid]);

  const handleFieldChange = useCallback((questionName, value) => {
    setEditValues((prev) => ({ ...prev, [questionName]: value }));
  }, []);

  const handleStartEdit = useCallback(
    async (section) => {
      if (!submission) return;
      // Fetch form questions with options (cached)
      // Only needed for non-plot sections (plot uses plot_field_specs)
      if (section !== "plot" && formQuestions.length === 0) {
        try {
          const res = await api.get(
            `/v1/odk/forms/${submission.form}/form_questions/`,
          );
          setFormQuestions(res.data);
        } catch {
          mapState.setToastMessage({
            message: "Failed to load form questions. Please try again.",
            type: "error",
          });
          return;
        }
      }

      const initial = {};
      if (section === "plot") {
        // Plot fields come from plot_field_specs
        // (region_field / sub_region_field config)
        const specs = submission?.plot_field_specs || {};
        for (const fields of Object.values(specs)) {
          for (const f of fields) {
            if (f.question_name) {
              initial[f.question_name] = f.raw_value ?? "";
            }
          }
        }
      } else {
        // Other sections use field_mapped_data
        const mapped = submission?.field_mapped_data || {};
        const stdNames = SECTION_FIELD_MAP[section] || [];
        for (const stdName of stdNames) {
          const entry = mapped[stdName];
          if (entry?.question_name) {
            initial[entry.question_name] = entry.raw_value ?? "";
          }
        }
      }
      setEditValues(initial);
      setEditingSection(section);
    },
    [submission, formQuestions.length, mapState],
  );

  const handleSave = useCallback(async () => {
    if (!plot?.submission_uuid) return;
    setIsSaving(true);
    try {
      const res = await api.patch(
        `/v1/odk/submissions/${plot.submission_uuid}/edit_data/`,
        { fields: editValues },
      );
      setSubmission(res.data);
      // Refresh plot + list for updated region/sub_region
      mapState.refetchSelectedPlot();
      mapState.refetch();
      setEditingSection(null);
      setEditValues({});
    } catch {
      mapState.setToastMessage({
        message: "Failed to save changes. Please try again.",
        type: "error",
      });
    } finally {
      setIsSaving(false);
    }
  }, [plot?.submission_uuid, editValues, mapState]);

  const handleCancelEdit = useCallback(() => {
    setEditingSection(null);
    setEditValues({});
  }, []);

  const getEditableFields = useCallback(
    (section) => {
      if (section === "plot") {
        // Plot fields come from plot_field_specs
        const specs = submission?.plot_field_specs || {};
        return Object.values(specs)
          .flat()
          .map((f) => ({
            questionName: f.question_name,
            label: f.label,
            rawValue: editValues[f.question_name] ?? "",
            type: f.type,
            options: f.options || [],
          }));
      }
      // Other sections use field_mapped_data
      const mapped = submission?.field_mapped_data || {};
      const stdNames = SECTION_FIELD_MAP[section] || [];
      return stdNames
        .map((stdName) => {
          const entry = mapped[stdName];
          if (!entry?.question_name) return null;
          const q = formQuestions.find((fq) => fq.name === entry.question_name);
          return {
            questionName: entry.question_name,
            label: entry.label,
            rawValue: editValues[entry.question_name] ?? "",
            type: entry.type,
            options: q?.options || [],
          };
        })
        .filter(Boolean);
    },
    [submission, formQuestions, editValues],
  );

  if (!plot) {
    if (isLoading) {
      return (
        <div className="flex h-full flex-col">
          <div className="flex items-center gap-2 border-b border-border p-4">
            <Skeleton className="h-8 w-8" />
            <Skeleton className="h-6 w-48" />
          </div>
          <div className="space-y-3 p-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </div>
      );
    }
    return null;
  }

  const status = getPlotStatus(plot);
  const resolved = submission?.resolved_data || {};
  const details = submission ? extractPlotDetails(submission) : null;
  const attachments = details?.attachments || [];
  const hasGeometry =
    plot.min_lat != null &&
    plot.max_lat != null &&
    plot.min_lon != null &&
    plot.max_lon != null;
  const centerLat = hasGeometry
    ? ((plot.min_lat + plot.max_lat) / 2).toFixed(6)
    : null;
  const centerLon = hasGeometry
    ? ((plot.min_lon + plot.max_lon) / 2).toFixed(6)
    : null;

  const hasTimeline = resolved?.start || resolved?.end;

  const handleSeeTitleDeed =
    attachments.length > 0 && onOpenTitleDeed
      ? () => onOpenTitleDeed(attachments)
      : undefined;

  const editProps = (section) => ({
    isEditing: editingSection === section,
    onEdit: () => handleStartEdit(section),
    onSave: handleSave,
    onCancel: handleCancelEdit,
    isSaving,
  });

  return (
    <div className="flex h-full flex-col">
      {/* Header card with tabs */}
      <PlotHeaderCard
        plotId={plot?.plot_id}
        mainPlotUid={plot?.main_plot_uid}
        status={status}
        flaggedReason={plot?.flagged_reason}
        lastCheckedBy={submission?.updated_by_name}
        lastCheckedAt={
          submission?.updated_at
            ? new Date(submission.updated_at).toLocaleDateString("en-GB")
            : undefined
        }
        attachmentCount={attachments.length}
        onBack={onBack}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {/* Tab content */}
      <ScrollArea className="min-h-0 flex-1 bg-muted">
        {isLoadingSub && (
          <div className="space-y-3 p-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        )}
        {!isLoadingSub && activeTab === "details" && (
          <div className="flex w-full flex-col gap-2 p-4">
            {/* Plot details summary */}
            <div className="flex flex-col gap-3 rounded-md border border-card-foreground/10 p-3 bg-card">
              <SectionHeader
                icon={Map}
                title="Plot details"
                {...editProps("plot")}
              />
              <Separator className="bg-muted-foreground/20" />
              {editingSection === "plot" ? (
                <div className="flex flex-col gap-3">
                  {getEditableFields("plot").map((f) => (
                    <EditableField
                      key={f.questionName}
                      {...f}
                      onChange={handleFieldChange}
                    />
                  ))}
                  {/* Area is read-only (computed) */}
                  <DataField label="Area (Ha)" value={details?.area} />
                </div>
              ) : (
                <DataFieldRow
                  fields={[
                    { label: "Region", value: plot?.region },
                    { label: "Sub-region", value: plot?.sub_region },
                    { label: "Area (Ha)", value: details?.area },
                  ]}
                />
              )}
            </div>

            {/* Timeline */}
            {hasTimeline && (
              <div className="flex rounded-md border border-card-foreground/10 pl-0 pr-3 bg-card">
                <div className="flex w-8 flex-col items-center py-3">
                  <div className="size-1.5 rounded-full bg-foreground/10" />
                  <div className="w-px flex-1 bg-foreground/10" />
                  <div className="size-1.5 rounded-full border border-foreground/10" />
                </div>
                <div className="flex flex-1 flex-col">
                  <TimelineRow
                    label="Start date:"
                    value={
                      resolved?.start
                        ? new Date(resolved.start).toLocaleDateString("en-GB")
                        : "—"
                    }
                  />
                  <TimelineRow
                    label="End date:"
                    value={
                      resolved?.end
                        ? new Date(resolved.end).toLocaleDateString("en-GB")
                        : "—"
                    }
                  />
                </div>
              </div>
            )}

            {/* Enumerator */}
            <PersonSection
              icon={User}
              title="Enumerator"
              name={
                editingSection === "enumerator"
                  ? undefined
                  : details?.enumerator?.name
              }
              fields={
                editingSection === "enumerator"
                  ? []
                  : [
                      {
                        label: "ID number",
                        value: details?.enumerator?.idNumber,
                      },
                    ]
              }
              {...editProps("enumerator")}
            >
              {editingSection === "enumerator" && (
                <div className="flex flex-col gap-3">
                  {getEditableFields("enumerator").map((f) => (
                    <EditableField
                      key={f.questionName}
                      {...f}
                      onChange={handleFieldChange}
                    />
                  ))}
                </div>
              )}
            </PersonSection>

            {/* Farmer */}
            <PersonSection
              icon={User}
              title="Farmer"
              name={
                editingSection === "farmer" ? undefined : details?.farmer?.name
              }
              subTitle={
                editingSection === "farmer"
                  ? null
                  : plot?.farmer_uid
                    ? `ID number: ${PREFIX_FARM_ID}${plot.farmer_uid}`
                    : null
              }
              fields={
                editingSection === "farmer"
                  ? []
                  : [
                      {
                        label: "Father's name",
                        value: details?.farmer?.fatherName,
                      },
                      {
                        label: "Grandfather's name",
                        value: details?.farmer?.grandfatherName,
                      },
                    ]
              }
              {...editProps("farmer")}
            >
              {editingSection === "farmer" ? (
                <div className="flex flex-col gap-3">
                  {getEditableFields("farmer").map((f) => (
                    <EditableField
                      key={f.questionName}
                      {...f}
                      onChange={handleFieldChange}
                    />
                  ))}
                </div>
              ) : (
                <>
                  <Separator className="bg-muted-foreground/20" />
                  {handleSeeTitleDeed ? (
                    <button
                      type="button"
                      onClick={handleSeeTitleDeed}
                      className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
                    >
                      <ImageIcon className="size-4" />
                      <span className="flex-1 text-left">Title deed</span>
                      <span className="flex items-center gap-1">
                        See data
                        <ArrowRight className="size-3.5" />
                      </span>
                    </button>
                  ) : (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground/50">
                      <ImageIcon className="size-4" />
                      <span>No title deed uploaded</span>
                    </div>
                  )}
                </>
              )}
            </PersonSection>

            {/* Open area mapping */}
            {hasGeometry && (
              <div className="flex flex-col gap-3 rounded-md border border-card-foreground/10 p-3 bg-card">
                <SectionHeader title="Open area mapping" />
                <a
                  href={`https://www.google.com/maps?q=${centerLat},${centerLon}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 rounded-md"
                >
                  <MapPin className="size-4 text-muted-foreground" />
                  <span className="text-sm">
                    {centerLat}, {centerLon}
                  </span>
                </a>
              </div>
            )}

            {/* Notes */}
            {details?.notes && (
              <div className="flex flex-col gap-3 rounded-md border border-card-foreground/10 p-3 bg-card">
                <SectionHeader title="Notes" />
                <p className="text-sm text-foreground">{details?.notes}</p>
              </div>
            )}

            {/* Rejection audit trail */}
            {submission?.rejection_audits?.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-sm font-medium">Rejection History</h3>
                <div className="space-y-2">
                  {submission.rejection_audits.map((audit) => (
                    <div
                      key={audit.id}
                      className="rounded-md border border-border p-3 space-y-1 bg-card"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <Badge variant="outline" className="text-xs">
                          {audit.reason_category_display}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {new Date(audit.rejected_at).toLocaleDateString(
                            "en-GB",
                          )}
                        </span>
                      </div>
                      {audit.reason_text && (
                        <p className="text-sm text-muted-foreground">
                          {audit.reason_text}
                        </p>
                      )}
                      <p className="text-xs text-muted-foreground">
                        by {audit.validator_name || "Unknown"}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Edit polygon button */}
            {hasGeometry && (
              <Button
                variant="outline"
                className="w-full"
                onClick={onStartEditing}
              >
                <span className="font-semibold">Edit polygon</span>
                <SquarePen className="ml-2 size-4" />
              </Button>
            )}
          </div>
        )}

        {!isLoadingSub && activeTab === "attachments" && (
          <div className="flex flex-col gap-3 p-4">
            {attachments.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No attachments
              </p>
            ) : (
              attachments.map((att, i) => (
                <AttachmentCard
                  key={att.filename || i}
                  filename={att.filename}
                  imageUrl={att.local_url}
                  caption={att.question_label}
                />
              ))
            )}
          </div>
        )}
      </ScrollArea>

      {/* Action buttons */}
      {(["pending", "flagged"].includes(status) || isResetting) && (
        <div className="flex gap-2 border-t border-border p-4 position-sticky bottom-0 bg-card">
          <Button
            className="flex-1 bg-status-approved text-white hover:bg-status-approved/90"
            onClick={onApprove}
          >
            Approve
          </Button>
          <Button variant="destructive" className="flex-1" onClick={onReject}>
            Reject
          </Button>
        </div>
      )}
      {["approved", "rejected"].includes(status) && !isResetting && (
        <div className="flex flex-col gap-2 border-t border-border p-4 position-sticky bottom-0 bg-card">
          <Button
            variant="outline"
            className="w-full"
            onClick={() => setIsResetting(true)}
          >
            Reset Approval
          </Button>
          <Button
            variant="outline"
            className="w-full"
            onClick={onRevertToPending}
          >
            Revert to Pending
          </Button>
        </div>
      )}
    </div>
  );
}
