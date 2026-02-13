"use client";

import { useState, useCallback } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { useForms } from "@/hooks/useForms";
import { usePlots } from "@/hooks/usePlots";
import { useMapState } from "@/hooks/useMapState";
import { toWktPolygon } from "@/lib/wkt-parser";
import { calculateBbox } from "@/lib/plot-utils";
import api from "@/lib/api";

import MapContainerDynamic from "@/components/map/map-container-dynamic";
import MapFilterBar from "@/components/map/map-filter-bar";
import PlotListPanel from "@/components/map/plot-list-panel";
import PlotDetailPanel from "@/components/map/plot-detail-panel";
import ApprovalDialog from "@/components/map/approval-dialog";
import RejectionDialog from "@/components/map/rejection-dialog";
import ToastNotification from "@/components/map/toast-notification";

export default function MapPage() {
  const { activeForm } = useForms();
  const { plots, count, isLoading, refetch } = usePlots({
    formId: activeForm?.asset_uid,
  });

  const mapState = useMapState({ plots });
  const [editedGeo, setEditedGeo] = useState(null);

  const handleApprove = useCallback(
    async () => {
      if (!mapState.selectedPlot) return;
      await api.patch(`/v1/odk/plots/${mapState.selectedPlot.uuid}/`, {
        is_draft: false,
      });
      mapState.setApprovalDialogOpen(false);
      mapState.handleBackToList();
      await refetch();
      mapState.setToastMessage("Plot approved successfully");
    },
    [mapState, refetch],
  );

  const handleReject = useCallback(
    async () => {
      if (!mapState.selectedPlot) return;
      // Currently no rejected status in backend, just log the intent
      mapState.setRejectionDialogOpen(false);
      mapState.handleBackToList();
      await refetch();
      mapState.setToastMessage("Plot rejected");
    },
    [mapState, refetch],
  );

  const handleSaveEdit = useCallback(async () => {
    if (!editedGeo || !mapState.editingPlotId) return;
    const wkt = toWktPolygon(editedGeo);
    const bbox = calculateBbox(editedGeo);
    await api.patch(`/v1/odk/plots/${mapState.editingPlotId}/`, {
      polygon_wkt: wkt,
      ...bbox,
    });
    setEditedGeo(null);
    mapState.handleCancelEditing();
    await refetch();
    mapState.setToastMessage("Geometry saved successfully");
  }, [editedGeo, mapState, refetch]);

  const handleCancelEdit = useCallback(() => {
    setEditedGeo(null);
    mapState.handleCancelEditing();
  }, [mapState]);

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
            onBack={mapState.handleBackToList}
            onApprove={() => mapState.setApprovalDialogOpen(true)}
            onReject={() => mapState.setRejectionDialogOpen(true)}
            onStartEditing={mapState.handleStartEditing}
          />
        )}
      </div>

      {/* Map Area */}
      <div className="relative flex-1">
        <MapFilterBar />
        <MapContainerDynamic
          plots={plots}
          selectedPlot={mapState.selectedPlot}
          editingPlotId={mapState.editingPlotId}
          editedGeo={editedGeo}
          setEditedGeo={setEditedGeo}
          onSelectPlot={mapState.handleSelectPlot}
          onSaveEdit={handleSaveEdit}
          onCancelEdit={handleCancelEdit}
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

      {/* Toast */}
      <ToastNotification
        message={mapState.toastMessage}
        onDismiss={() => mapState.setToastMessage(null)}
      />
    </div>
  );
}
