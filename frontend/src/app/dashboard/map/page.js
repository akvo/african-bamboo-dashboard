"use client";

import { useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Skeleton } from "@/components/ui/skeleton";
import { useForms } from "@/hooks/useForms";
import { usePlots } from "@/hooks/usePlots";
import { useMapState } from "@/hooks/useMapState";
import { toWktPolygon } from "@/lib/wkt-parser";
import { calculateBbox } from "@/lib/plot-utils";
import api from "@/lib/api";
import { DEFAULT_BASEMAP } from "@/lib/basemap-config";

import MapContainerDynamic from "@/components/map/map-container-dynamic";
import MapFilterBar from "@/components/map/map-filter-bar";
import PlotListPanel from "@/components/map/plot-list-panel";
import PlotDetailPanel from "@/components/map/plot-detail-panel";
import ApprovalDialog from "@/components/map/approval-dialog";
import RejectionDialog from "@/components/map/rejection-dialog";
import SaveEditDialog from "@/components/map/save-edit-dialog";
import ToastNotification from "@/components/map/toast-notification";

export default function MapPage() {
  const searchParams = useSearchParams();
  const { activeForm } = useForms();
  const { plots, count, isLoading, refetch } = usePlots({
    formId: activeForm?.asset_uid,
  });

  const mapState = useMapState({
    plots,
    initialPlotId: searchParams.get("plot"),
  });

  const [editedGeo, setEditedGeo] = useState(null);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [basemap, setBasemap] = useState(DEFAULT_BASEMAP);
  const [isResetting, setIsResetting] = useState(false);

  const handleApprove = useCallback(
    async (notes) => {
      if (!mapState.selectedPlot?.submission_uuid) return;
      try {
        await api.patch(
          `/v1/odk/submissions/${mapState.selectedPlot.submission_uuid}/`,
          { approval_status: 1, reviewer_notes: notes || "" },
        );
        mapState.setApprovalDialogOpen(false);
        mapState.handleBackToList();
        await refetch();
        mapState.setToastMessage("Plot approved successfully");
      } catch {
        mapState.setApprovalDialogOpen(false);
        mapState.setToastMessage("Failed to approve plot. Please try again.");
      }
    },
    [mapState, refetch],
  );

  const handleReject = useCallback(
    async (reason) => {
      if (!mapState.selectedPlot?.submission_uuid) return;
      try {
        await api.patch(
          `/v1/odk/submissions/${mapState.selectedPlot.submission_uuid}/`,
          { approval_status: 2, reviewer_notes: reason },
        );
        mapState.setRejectionDialogOpen(false);
        mapState.handleBackToList();
        await refetch();
        mapState.setToastMessage("Plot rejected");
      } catch {
        mapState.setRejectionDialogOpen(false);
        mapState.setToastMessage("Failed to reject plot. Please try again.");
      }
    },
    [mapState, refetch],
  );

  const handleSaveEdit = useCallback(async () => {
    if (!editedGeo || !mapState.editingPlotId) return;
    const wkt = toWktPolygon(editedGeo);
    const bbox = calculateBbox(editedGeo);
    try {
      await api.patch(`/v1/odk/plots/${mapState.editingPlotId}/`, {
        polygon_wkt: wkt,
        ...bbox,
      });
      setEditedGeo(null);
      mapState.handleCancelEditing();
      await refetch();
      mapState.setToastMessage("Geometry saved successfully");
    } catch {
      mapState.setToastMessage("Failed to save geometry. Please try again.");
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
      await refetch();
      mapState.setToastMessage("Polygon reset to original");
    } catch {
      mapState.setToastMessage("Failed to reset polygon. Please try again.");
    } finally {
      setIsResetting(false);
    }
  }, [mapState, refetch]);

  return (
    <div className="-m-6 flex h-[calc(100%+3rem)] overflow-hidden">
      {/* Left Panel */}
      <div className="hidden w-[380px] shrink-0 flex-col border-r border-border bg-card md:flex">
        {isLoading ? (
          <div className="space-y-3 p-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : mapState.panelMode === "list" ? (
          <PlotListPanel
            plots={plots}
            count={count}
            activeTab={mapState.activeTab}
            sortBy={mapState.sortBy}
            selectedPlotId={mapState.selectedPlotId}
            onTabChange={mapState.setActiveTab}
            onSortChange={mapState.setSortBy}
            onSelectPlot={mapState.handleSelectPlot}
          />
        ) : (
          <PlotDetailPanel
            plot={mapState.selectedPlot}
            onBack={() => {
              mapState.handleBackToList();
              // redirect to base map URL without plot query param if exists
              if (searchParams.get("plot")) {
                const url = new URL(window.location.href);
                url.searchParams.delete("plot");
                window.history.replaceState({}, "", url);
              }
            }}
            onApprove={() => mapState.setApprovalDialogOpen(true)}
            onReject={() => mapState.setRejectionDialogOpen(true)}
            onStartEditing={mapState.handleStartEditing}
          />
        )}
      </div>

      {/* Map Area */}
      <div className="relative flex-1">
        <MapFilterBar basemap={basemap} onBasemapChange={setBasemap} />
        <MapContainerDynamic
          plots={plots}
          selectedPlot={mapState.selectedPlot}
          editingPlotId={mapState.editingPlotId}
          editedGeo={editedGeo}
          setEditedGeo={setEditedGeo}
          onSelectPlot={mapState.handleSelectPlot}
          onSaveEdit={handleSaveClick}
          onCancelEdit={handleCancelEdit}
          onReset={handleResetPolygon}
          isResetting={isResetting}
          basemap={basemap}
        />
      </div>

      {/* Dialogs */}
      <ApprovalDialog
        open={mapState.approvalDialogOpen}
        onOpenChange={mapState.setApprovalDialogOpen}
        onConfirm={handleApprove}
      />
      <RejectionDialog
        open={mapState.rejectionDialogOpen}
        onOpenChange={mapState.setRejectionDialogOpen}
        onConfirm={handleReject}
      />
      <SaveEditDialog
        open={saveDialogOpen}
        onOpenChange={setSaveDialogOpen}
        onConfirm={async () => {
          await handleSaveEdit();
          setSaveDialogOpen(false);
        }}
      />

      {/* Toast */}
      <ToastNotification
        message={mapState.toastMessage}
        onDismiss={() => mapState.setToastMessage(null)}
      />
    </div>
  );
}
