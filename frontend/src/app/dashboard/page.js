"use client";

import { useCallback, useMemo, useState } from "react";
import { Download, Loader2, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DashboardHeader } from "@/components/dashboard-header";
import { StatCard } from "@/components/stat-card";
import { FilterBar, getDateRange } from "@/components/filter-bar";
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

const stats = [];

const DashboardPage = () => {
  const { forms, activeForm, setActiveForm } = useForms();
  const { startExport, isExporting } = useExport();

  const [activeTab, setActiveTab] = useState("all");
  const [search, setSearch] = useState("");
  const [region, setRegion] = useState("");
  const [subRegion, setSubRegion] = useState("");
  const [datePreset, setDatePreset] = useState("");
  const [dynamicValues, setDynamicValues] = useState({});

  const { regions, sub_regions, dynamic_filters } = useFilterOptions({
    formId: activeForm?.asset_uid,
    region,
  });

  const { start: startDate, end: endDate } = useMemo(
    () => getDateRange(datePreset),
    [datePreset],
  );

  const { data, questions, count, isLoading, page, totalPages, setPage } =
    useSubmissions({
      assetUid: activeForm?.asset_uid,
      status: activeTab,
      search,
      region,
      subRegion,
      startDate,
      endDate,
      dynamicFilters: dynamicValues,
    });
  const { plots } = usePlots({ formId: activeForm?.asset_uid });

  const handleReset = useCallback(() => {
    setRegion("");
    setSubRegion("");
    setDatePreset("");
    setDynamicValues({});
    setSearch("");
    setActiveTab("all");
  }, []);

  const handleExport = () => {
    startExport({
      formId: activeForm?.asset_uid,
      status: activeTab,
      search,
      region,
      subRegion,
      start_date: startDate,
      end_date: endDate,
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
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <StatCard key={stat.title} {...stat} />
        ))}
      </div>

      {/* Filters */}
      <FilterBar
        regions={regions}
        sub_regions={sub_regions}
        dynamicFilters={dynamic_filters}
        region={region}
        subRegion={subRegion}
        datePreset={datePreset}
        dynamicValues={dynamicValues}
        onRegionChange={(v) => {
          setRegion(v);
          setSubRegion("");
        }}
        onSubRegionChange={setSubRegion}
        onDatePresetChange={setDatePreset}
        onDynamicFilterChange={(name, val) =>
          setDynamicValues((prev) => ({ ...prev, [name]: val }))
        }
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
          <Button
            variant="outline"
            size="sm"
            onClick={handleExport}
            disabled={isExporting}
          >
            {isExporting ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Exporting...
              </>
            ) : (
              <>
                <Download className="size-4" />
                Export data
              </>
            )}
          </Button>
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
