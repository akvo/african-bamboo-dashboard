"use client";

import { useState, useCallback, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useForms } from "@/hooks/useForms";
import { useMapState } from "@/hooks/useMapState";
import { useFilterOptions } from "@/hooks/useFilterOptions";
import { toWktPolygon } from "@/lib/wkt-parser";
import { calculateBbox } from "@/lib/plot-utils";
import api from "@/lib/api";
import { CheckCircle2, XCircle, Save } from "lucide-react";

import MapContainerDynamic from "@/components/map/map-container-dynamic";
import { FilterBar } from "@/components/filter-bar";
import PlotListPanel from "@/components/map/plot-list-panel";
import PlotDetailPanel from "@/components/map/plot-detail-panel";
import ConfirmDialog from "@/components/map/confirm-dialog";
import TitleDeedViewer from "@/components/map/title-deed-viewer";
import ToastNotification from "@/components/map/toast-notification";

export default function MapPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { activeForm, isChanged, setIsChanged } = useForms();
  const mapState = useMapState();
  const { plots, count, isLoading, refetch, selectedPlotId } = mapState;

  const { regions, sub_regions, dynamic_filters } = useFilterOptions({
    formId: activeForm?.asset_uid,
    region: mapState.region,
  });

  // Sync URL plot param → selectedPlotId (URL is source of truth)
  useEffect(() => {
    const plotId = searchParams.get("plot") || null;
    if (plotId !== selectedPlotId) {
      mapState.setSelectedPlotId(plotId);
    }
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSelectPlot = useCallback(
    (plotUuid) => {
      mapState.handleSelectPlot(plotUuid);
      if (plotUuid) {
        router.replace(`/dashboard/map?plot=${plotUuid}`, { scroll: false });
      }
    },
    [mapState, router],
  );

  const [editedGeo, setEditedGeo] = useState(null);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [titleDeedAttachments, setTitleDeedAttachments] = useState(null);

  // Close title deed viewer when selected plot changes
  useEffect(() => {
    setTitleDeedAttachments(null);
  }, [mapState.selectedPlotId]);

  useEffect(() => {
    if (isChanged) {
      mapState.setSelectedPlotId(null);
      refetch();
      setIsChanged(false);
    }
  }, [isChanged, setIsChanged, mapState, refetch]);

  const handleApprove = useCallback(async () => {
    if (!mapState.selectedPlot?.submission_uuid) {
      return;
    }
    try {
      await api.patch(
        `/v1/odk/submissions/${mapState.selectedPlot.submission_uuid}/`,
        { approval_status: 1 },
      );
      await Promise.all([refetch(), mapState.refetchSelectedPlot()]);
      mapState.setApprovalDialogOpen(false);
      mapState.setToastMessage("Plot approved successfully");
    } catch {
      mapState.setApprovalDialogOpen(false);
      mapState.setToastMessage({
        message: "Failed to approve plot. Please try again.",
        type: "error",
      });
    }
  }, [mapState, refetch]);

  const handleReject = useCallback(
    async ({ selectValue, notes }) => {
      if (!mapState.selectedPlot?.submission_uuid) {
        return;
      }
      try {
        await api.patch(
          `/v1/odk/submissions/${mapState.selectedPlot.submission_uuid}/`,
          {
            approval_status: 2,
            reason_category: selectValue,
            reason_text: notes || "",
          },
        );
        await Promise.all([refetch(), mapState.refetchSelectedPlot()]);
        mapState.setRejectionDialogOpen(false);
        mapState.setToastMessage("Plot rejected");
      } catch {
        mapState.setRejectionDialogOpen(false);
        mapState.setToastMessage({
          message: "Failed to reject plot. Please try again.",
          type: "error",
        });
      }
    },
    [mapState, refetch],
  );

  const handleRevertToPending = useCallback(async () => {
    if (!mapState.selectedPlot?.submission_uuid) {
      return;
    }
    try {
      await api.patch(
        `/v1/odk/submissions/${mapState.selectedPlot.submission_uuid}/`,
        { approval_status: null },
      );
      await Promise.all([refetch(), mapState.refetchSelectedPlot()]);
      mapState.setToastMessage("Plot reverted to pending");
    } catch {
      mapState.setToastMessage({
        message: "Failed to revert. Please try again.",
        type: "error",
      });
    }
  }, [mapState, refetch]);

  const handleSaveEdit = useCallback(async () => {
    if (!editedGeo || !mapState.editingPlotId) return;
    const wkt = toWktPolygon(editedGeo);
    const bbox = calculateBbox(editedGeo);
    try {
      await api.patch(`/v1/odk/plots/${mapState.editingPlotId}/`, {
        polygon_wkt: wkt,
        ...bbox,
      });
      setSaveDialogOpen(false);
      setEditedGeo(null);
      mapState.handleCancelEditing();
      await Promise.all([refetch(), mapState.refetchSelectedPlot()]);
      mapState.setToastMessage("Geometry saved. Syncing to Kobo...");
    } catch {
      mapState.setToastMessage({
        message: "Failed to save geometry. Please try again.",
        type: "error",
      });
    }
  }, [editedGeo, mapState, refetch]);

  const handleSaveClick = useCallback(() => {
    setSaveDialogOpen(true);
  }, []);

  const handleCancelEdit = useCallback(() => {
    setEditedGeo(null);
    mapState.handleCancelEditing();
  }, [mapState]);

  const handleResetPolygon = useCallback(async () => {
    if (!mapState.editingPlotId) return;
    setIsResetting(true);
    try {
      await api.post(`/v1/odk/plots/${mapState.editingPlotId}/reset_polygon/`);
      setEditedGeo(null);
      await Promise.all([refetch(), mapState.refetchSelectedPlot()]);
      mapState.setToastMessage("Polygon reset to original. Syncing to Kobo...");
    } catch {
      mapState.setToastMessage({
        message: "Failed to reset polygon. Please try again.",
        type: "error",
      });
    } finally {
      setIsResetting(false);
    }
  }, [mapState, refetch]);

  return (
    <div className="-m-6 flex h-[calc(100%+3rem)] flex-col overflow-hidden">
      <div className="flex min-h-0 flex-1">
        {/* Left Panel */}
        <div className="hidden md:flex w-1/2 max-w-[400px] shrink-0 flex-col overflow-hidden border-r border-border bg-card">
          {mapState.selectedPlotId ? (
            <PlotDetailPanel
              plot={mapState.selectedPlot}
              isLoading={mapState.isLoadingPlot}
              onBack={() => {
                mapState.handleBackToList();
                router.replace("/dashboard/map", { scroll: false });
              }}
              onApprove={() => mapState.setApprovalDialogOpen(true)}
              onReject={() => mapState.setRejectionDialogOpen(true)}
              onRevertToPending={handleRevertToPending}
              onStartEditing={mapState.handleStartEditing}
              onOpenTitleDeed={(atts) => setTitleDeedAttachments(atts)}
            />
          ) : (
            <PlotListPanel
              plots={plots}
              count={count}
              isLoading={isLoading}
              activeTab={mapState.activeTab}
              sortBy={mapState.sortBy}
              search={mapState.searchInput}
              selectedPlotId={mapState.selectedPlotId}
              onTabChange={mapState.setActiveTab}
              onSortChange={mapState.setSortBy}
              onSearchChange={mapState.handleSearchChange}
              onSelectPlot={handleSelectPlot}
            />
          )}
        </div>

        {/* Map Area */}
        <div className="relative flex-1">
          {/* Filters */}
          <div className="w-full min-h-[57px] border-b border-border px-4 py-2">
            <FilterBar
              regions={regions}
              sub_regions={sub_regions}
              dynamicFilters={dynamic_filters}
              region={mapState.region}
              subRegion={mapState.subRegion}
              startDate={mapState.startDate}
              endDate={mapState.endDate}
              dynamicValues={mapState.dynamicValues}
              onRegionChange={(v) => {
                mapState.setSelectedPlotId(null);
                router.replace("/dashboard/map", { scroll: false });
                mapState.setRegion(v);
                mapState.setSubRegion("");
              }}
              onSubRegionChange={(v) => {
                mapState.setSelectedPlotId(null);
                router.replace("/dashboard/map", { scroll: false });
                mapState.setSubRegion(v);
              }}
              onDateRangeChange={(from, to) => {
                mapState.setSelectedPlotId(null);
                router.replace("/dashboard/map", { scroll: false });
                mapState.setStartDate(from);
                mapState.setEndDate(to);
              }}
              onDynamicFilterChange={(name, val) => {
                mapState.setSelectedPlotId(null);
                router.replace("/dashboard/map", { scroll: false });
                mapState.setDynamicValues((prev) => ({ ...prev, [name]: val }));
              }}
              onReset={() => {
                mapState.handleResetFilters();
                router.replace("/dashboard/map", { scroll: false });
              }}
            />
          </div>
          <MapContainerDynamic
            plots={plots}
            selectedPlot={mapState.selectedPlot}
            editingPlotId={mapState.editingPlotId}
            editedGeo={editedGeo}
            setEditedGeo={setEditedGeo}
            onSelectPlot={handleSelectPlot}
            onSaveEdit={handleSaveClick}
            onCancelEdit={handleCancelEdit}
            onReset={handleResetPolygon}
            isResetting={isResetting}
            onNotify={mapState.setToastMessage}
          />
          <TitleDeedViewer
            open={titleDeedAttachments !== null}
            onClose={() => setTitleDeedAttachments(null)}
            attachments={titleDeedAttachments || []}
          />
        </div>
      </div>

      {/* Dialogs */}
      <ConfirmDialog
        open={mapState.approvalDialogOpen}
        onOpenChange={mapState.setApprovalDialogOpen}
        onConfirm={handleApprove}
        icon={CheckCircle2}
        iconClassName="text-status-approved"
        iconBgClassName="bg-status-approved/15"
        title="Confirm Approval"
        description="Approve this plot to confirm the boundary mapping is valid."
        confirmLabel="Confirm"
        confirmingLabel="Approving..."
        confirmClassName="bg-status-approved text-white hover:bg-status-approved/90"
      />
      <ConfirmDialog
        open={mapState.rejectionDialogOpen}
        onOpenChange={mapState.setRejectionDialogOpen}
        onConfirm={handleReject}
        icon={XCircle}
        iconClassName="text-status-rejected"
        iconBgClassName="bg-status-rejected/15"
        title="Reject Plot"
        description="Provide a reason for rejecting this plot boundary."
        confirmLabel="Reject"
        confirmingLabel="Rejecting..."
        confirmVariant="destructive"
        select={{
          label: "Rejection category *",
          placeholder: "Select a category...",
          required: true,
          options: [
            { value: "polygon_error", label: "Polygon Error" },
            { value: "overlap", label: "Overlap" },
            { value: "duplicate", label: "Duplicate Submission" },
            { value: "other", label: "Other" },
          ],
        }}
        textarea={{
          label: "Additional details",
          placeholder: "Optional explanation...",
        }}
      />
      <ConfirmDialog
        open={saveDialogOpen}
        onOpenChange={setSaveDialogOpen}
        onConfirm={handleSaveEdit}
        icon={Save}
        title="Save polygon changes?"
        description="This will overwrite the current polygon geometry. The changes will also be synced to Kobo."
        confirmLabel="Confirm Save"
        confirmingLabel="Saving..."
      />

      {/* Toast */}
      <ToastNotification
        message={mapState.toast?.message}
        type={mapState.toast?.type}
        onDismiss={() => mapState.setToastMessage(null)}
      />
    </div>
  );
}
