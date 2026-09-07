"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useForms } from "@/hooks/useForms";
import { useMapState } from "@/hooks/useMapState";
import { useFilterOptions } from "@/hooks/useFilterOptions";
import { toWktPolygon } from "@/lib/wkt-parser";
import { calculateBbox } from "@/lib/plot-utils";
import api from "@/lib/api";
import { CheckCircle2, XCircle, Save, Trash2 } from "lucide-react";

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

  const { regions, sub_regions, dynamic_filters, available_filters } =
    useFilterOptions({
      formId: activeForm?.asset_uid,
      region: mapState.region,
      allEligible: true,
    });

  // Sync URL plot param → selectedPlotId (URL is source of truth)
  useEffect(() => {
    const plotId = searchParams.get("plot") || null;
    if (plotId !== selectedPlotId) {
      mapState.handleSelectPlot(plotId);
    }
  }, [searchParams, selectedPlotId, mapState]);

  const handleSelectPlot = useCallback(
    (plotUuid) => {
      if (mapState.editingPlotId && plotUuid !== mapState.editingPlotId) {
        return;
      }
      mapState.handleSelectPlot(plotUuid);
      if (plotUuid) {
        router.replace(`/dashboard/map?plot=${plotUuid}`, { scroll: false });
      }
    },
    [mapState, router],
  );

  const [editedGeo, setEditedGeo] = useState(null);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [titleDeedAttachments, setTitleDeedAttachments] = useState(null);
  // Bumped when the Telegram delivery status changes, so the
  // detail panel re-fetches the submission that carries it.
  const [notifyRefresh, setNotifyRefresh] = useState(0);

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

  // The PATCH returns before the Kobo sync and the Telegram
  // send have even started, so delivery is reported in a
  // second stage. Blocking the dialog on it would be wrong:
  // a legitimate retry can take minutes.
  const NOTIFY_POLL_MS = 3000;
  const NOTIFY_MAX_POLLS = 8;

  const pollTimerRef = useRef(null);
  const pollCancelledRef = useRef(false);

  const stopNotifyPoll = useCallback(() => {
    pollCancelledRef.current = true;
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  // Cancel an in-flight poll when the user navigates away or
  // selects another plot.
  useEffect(() => stopNotifyPoll, [stopNotifyPoll]);
  useEffect(() => {
    stopNotifyPoll();
  }, [mapState.selectedPlotId, stopNotifyPoll]);

  const pollNotificationStatus = useCallback(
    (submissionUuid) => {
      stopNotifyPoll();
      pollCancelledRef.current = false;
      let tries = 0;

      const tick = async () => {
        if (pollCancelledRef.current) {
          return;
        }
        tries += 1;
        let status = null;
        try {
          const { data } = await api.get(
            `/v1/odk/submissions/${submissionUuid}/`,
          );
          status = data?.rejection_audits?.[0]?.telegram_status;
        } catch {
          // A dropped poll is not a delivery failure; retry.
        }
        if (pollCancelledRef.current) {
          return;
        }

        if (status === "sent") {
          setNotifyRefresh((n) => n + 1);
          mapState.setToastMessage("Field team notified on Telegram");
          return;
        }
        if (status === "sync_failed") {
          setNotifyRefresh((n) => n + 1);
          mapState.setToastMessage({
            message:
              "Rejection saved locally, but it did not reach " +
              "KoboToolbox, so the field team was not notified.",
            type: "error",
          });
          return;
        }
        if (status === "failed") {
          setNotifyRefresh((n) => n + 1);
          mapState.setToastMessage({
            message:
              "Rejection saved, but the Telegram notification " +
              "could not be delivered.",
            type: "warning",
          });
          return;
        }
        if (status === "disabled") {
          return;
        }
        if (tries >= NOTIFY_MAX_POLLS) {
          setNotifyRefresh((n) => n + 1);
          mapState.setToastMessage({
            message:
              "Rejection saved. The notification is still sending " +
              "and will retry automatically.",
            type: "warning",
          });
          return;
        }
        pollTimerRef.current = setTimeout(tick, NOTIFY_POLL_MS);
      };

      pollTimerRef.current = setTimeout(tick, NOTIFY_POLL_MS);
    },
    [mapState, stopNotifyPoll],
  );

  const handleReject = useCallback(
    async ({ selectValue, notes }) => {
      const submissionUuid = mapState.selectedPlot?.submission_uuid;
      if (!submissionUuid) {
        return;
      }
      try {
        await api.patch(`/v1/odk/submissions/${submissionUuid}/`, {
          approval_status: 2,
          reason_category: selectValue,
          reason_text: notes || "",
        });
        await Promise.all([refetch(), mapState.refetchSelectedPlot()]);
        mapState.setRejectionDialogOpen(false);

        // Stage 1: certain and immediate. Only promise a
        // notification when one is actually going out —
        // telegram_status is "disabled" when the integration
        // is switched off, and we must not imply a message
        // that was never configured.
        let status = null;
        try {
          const { data } = await api.get(
            `/v1/odk/submissions/${submissionUuid}/`,
          );
          status = data?.rejection_audits?.[0]?.telegram_status;
        } catch {
          // Fall through to the plain confirmation.
        }
        if (status && status !== "disabled") {
          mapState.setToastMessage("Plot rejected. Notifying field team…");
          pollNotificationStatus(submissionUuid);
        } else {
          mapState.setToastMessage("Plot rejected");
        }
      } catch {
        mapState.setRejectionDialogOpen(false);
        mapState.setToastMessage({
          message: "Failed to reject plot. Please try again.",
          type: "error",
        });
      }
    },
    [mapState, refetch, pollNotificationStatus],
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

  // Only offered for a submission Kobo no longer has. The
  // backend refuses this for any live submission, since the
  // cascade takes rejection history and the Plot ID link
  // with it.
  const handleConfirmDeleteSubmission = useCallback(async () => {
    const submissionUuid = mapState.selectedPlot?.submission_uuid;
    if (!submissionUuid) {
      return;
    }
    try {
      await api.delete(`/v1/odk/submissions/${submissionUuid}/`);
      setDeleteDialogOpen(false);
      mapState.setSelectedPlotId(null);
      router.replace("/dashboard/map", { scroll: false });
      await refetch();
      mapState.setToastMessage("Submission deleted");
    } catch (err) {
      setDeleteDialogOpen(false);
      mapState.setToastMessage({
        message:
          err?.response?.data?.detail ||
          "Failed to delete submission. Please try again.",
        type: "error",
      });
    }
  }, [mapState, refetch, router]);

  const handleSaveEdit = useCallback(async () => {
    if (!editedGeo || !mapState.editingPlotId) {
      return;
    }
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
    if (!mapState.editingPlotId) {
      return;
    }
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
              onNotify={(t) => {
                mapState.setToastMessage(t);
                setNotifyRefresh((n) => n + 1);
              }}
              refreshKey={notifyRefresh}
              onDeleteSubmission={() => setDeleteDialogOpen(true)}
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
              availableFilters={available_filters}
              activeFilterFields={mapState.activeFilterFields}
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
              onActiveFilterFieldsChange={mapState.setActiveFilterFields}
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
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleConfirmDeleteSubmission}
        icon={Trash2}
        iconClassName="text-status-rejected"
        iconBgClassName="bg-status-rejected/15"
        title="Delete this submission?"
        description={
          "This submission no longer exists in KoboToolbox. " +
          "Deleting it here also removes its plot, its " +
          "rejection history and its Plot ID link. This " +
          "cannot be undone."
        }
        confirmLabel="Delete permanently"
        confirmingLabel="Deleting..."
        confirmVariant="destructive"
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
