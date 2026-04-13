"use client";

import { useCallback, useState } from "react";
import { ChevronDown, Download, Loader2, Map, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DashboardHeader } from "@/components/dashboard-header";
import { FilterBar } from "@/components/filter-bar";
import { StatTabs } from "@/components/stat-tabs";
import { SubmissionsTable } from "@/components/submissions-table";
import { TablePagination } from "@/components/table-pagination";
import { useForms } from "@/hooks/useForms";
import { usePlots } from "@/hooks/usePlots";
import { useSubmissions } from "@/hooks/useSubmissions";
import { useFilterOptions } from "@/hooks/useFilterOptions";
import { useExport } from "@/hooks/useExport";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useMapState } from "@/hooks/useMapState";
import { useStats } from "@/hooks/useStats";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardAction,
} from "@/components/ui/card";

const DashboardPage = () => {
  const { forms, activeForm, setActiveForm } = useForms();
  const { startExport, isExporting } = useExport();

  const {
    region,
    subRegion,
    startDate,
    endDate,
    dynamicValues,
    activeFilterFields,
    setRegion,
    setSubRegion,
    setStartDate,
    setEndDate,
    setDynamicValues,
    setActiveFilterFields,
    handleResetFilters,
  } = useMapState();

  const { stats } = useStats({
    formId: activeForm?.asset_uid,
    region,
    subRegion,
    startDate: startDate ? startDate.getTime() : null,
    endDate: endDate ? endDate.getTime() : null,
    dynamicFilters: dynamicValues,
  });

  const [activeTab, setActiveTab] = useState("all");
  const [statsTab, setStatsTab] = useState("plot");
  const [approvalTab, setApprovalTab] = useState("percentage");
  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState(null);

  const { regions, sub_regions, dynamic_filters, available_filters } =
    useFilterOptions({
      formId: activeForm?.asset_uid,
      region,
      allEligible: true,
    });

  const startMs = startDate ? startDate.getTime() : null;
  const endMs = endDate ? endDate.getTime() : null;

  const {
    data,
    questions,
    sortableFields,
    count,
    isLoading,
    page,
    totalPages,
    setPage,
  } = useSubmissions({
    assetUid: activeForm?.asset_uid,
    status: activeTab,
    search,
    region,
    subRegion,
    startDate: startMs,
    endDate: endMs,
    dynamicFilters: dynamicValues,
    ordering,
  });
  const { plots } = usePlots({ formId: activeForm?.asset_uid });

  const handleReset = useCallback(() => {
    handleResetFilters();
    setOrdering(null);
    setSearch("");
    setActiveTab("all");
  }, [handleResetFilters]);

  const handleExport = (format) => {
    startExport({
      formId: activeForm?.asset_uid,
      format,
      status: activeTab,
      search,
      region,
      subRegion,
      start_date: startMs,
      end_date: endMs,
      dynamic_filters: dynamicValues,
    });
  };

  function handleFormChange(assetUid) {
    const form = forms.find((f) => f.asset_uid === assetUid);
    if (form) {
      setActiveForm(form);
      handleReset();
    }
  }

  return (
    <div className="space-y-6">
      <DashboardHeader />
      {/* Stats Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-md font-medium text-foreground">
              Total submissions
            </CardTitle>
            <CardAction>
              <StatTabs
                value={statsTab}
                onChange={setStatsTab}
                ariaLabel="Stats unit toggle"
                options={[
                  {
                    value: "plot",
                    icon: Map,
                    ariaLabel: "Show plot count",
                  },
                  {
                    value: "ha",
                    label: "Ha",
                    ariaLabel: "Show hectares",
                  },
                ]}
              />
            </CardAction>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {statsTab === "plot"
                ? (stats?.total_plots ?? 0).toLocaleString()
                : (stats?.total_area_ha ?? 0).toLocaleString()}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {statsTab === "plot"
                ? "Amount of plots mapped"
                : "Amount of hectares mapped"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-md font-medium text-foreground">
              {approvalTab === "percentage"
                ? "Percentage approved on first submission"
                : "Hectares approved on first submission"}
            </CardTitle>
            <CardAction>
              <StatTabs
                value={approvalTab}
                onChange={setApprovalTab}
                ariaLabel="Approval unit toggle"
                options={[
                  {
                    value: "percentage",
                    label: "%",
                    ariaLabel: "Show approval percentage",
                  },
                  {
                    value: "ha",
                    label: "Ha",
                    ariaLabel: "Show approved hectares",
                  },
                ]}
              />
            </CardAction>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {approvalTab === "percentage"
                ? `${stats?.approval_percentage ?? 0}%`
                : (stats?.approved_area_ha ?? 0).toLocaleString()}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {approvalTab === "percentage"
                ? "Of plots out of 100%"
                : "Hectares approved"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-md font-medium text-foreground">
              Number of items currently requiring review
            </CardTitle>
            {/* TODO: wire up MoreVertical menu actions
            <CardAction>
              <Button variant="ghost" size="icon-xs" aria-label="More options">
                <MoreVertical className="size-4" />
              </Button>
            </CardAction>
            */}
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {(stats?.pending_count ?? 0).toLocaleString()}
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {stats?.pending_area_ha
                ? `${stats.pending_area_ha.toLocaleString()} hectares to map`
                : ""}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <FilterBar
        regions={regions}
        sub_regions={sub_regions}
        dynamicFilters={dynamic_filters}
        availableFilters={available_filters}
        activeFilterFields={activeFilterFields}
        region={region}
        subRegion={subRegion}
        startDate={startDate}
        endDate={endDate}
        dynamicValues={dynamicValues}
        onRegionChange={(v) => {
          setRegion(v);
          setSubRegion("");
        }}
        onSubRegionChange={setSubRegion}
        onDateRangeChange={(from, to) => {
          setStartDate(from);
          setEndDate(to);
        }}
        onDynamicFilterChange={(name, val) =>
          setDynamicValues((prev) => ({ ...prev, [name]: val }))
        }
        onActiveFilterFieldsChange={setActiveFilterFields}
        onReset={handleReset}
      />

      {/* Form Section Header */}
      {activeForm && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <Select
              value={activeForm?.asset_uid || ""}
              onValueChange={handleFormChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="Form" />
              </SelectTrigger>
              <SelectContent>
                {forms.map((form) => (
                  <SelectItem key={form.asset_uid} value={form.asset_uid}>
                    {form.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Badge variant="secondary">{count} Data points</Badge>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" disabled={isExporting}>
                {isExporting ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Exporting...
                  </>
                ) : (
                  <>
                    <Download className="size-4" />
                    Export data
                    <ChevronDown className="size-3" />
                  </>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleExport("shp")}>
                Shapefile (.shp)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport("geojson")}>
                GeoJSON (.geojson)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport("xlsx")}>
                Clean Data (.xlsx)
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}

      {/* Table Controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="all">View all</TabsTrigger>
            <TabsTrigger value="approved">Approved</TabsTrigger>
            <TabsTrigger value="pending">On Hold</TabsTrigger>
            <TabsTrigger value="rejected">Rejected</TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="relative w-full sm:w-64">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {/* Submissions Table */}
      <SubmissionsTable
        data={data}
        isLoading={isLoading}
        plots={plots}
        questions={questions}
        ordering={ordering}
        onSort={setOrdering}
        sortableFields={sortableFields}
      />

      {/* Pagination */}
      {totalPages > 1 && (
        <TablePagination
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
        />
      )}
    </div>
  );
};

export default DashboardPage;
