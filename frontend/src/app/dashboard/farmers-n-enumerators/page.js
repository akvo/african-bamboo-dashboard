"use client";

import { useState, useEffect, useCallback } from "react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import { useForms } from "@/hooks/useForms";
import api from "@/lib/api";
import { useMapState } from "@/hooks/useMapState";

const PAGE_SIZE = 10;

function usePaginatedData(endpoint, formId) {
  const [data, setData] = useState([]);
  const [count, setCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  const fetchData = useCallback(async () => {
    if (!formId) {
      setData([]);
      setCount(0);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(offset),
        form_id: formId,
      });
      if (search) params.set("search", search);
      const res = await api.get(`${endpoint}?${params}`);
      setData(res.data?.results || []);
      setCount(res.data?.count ?? 0);
    } catch {
      setData([]);
      setCount(0);
    } finally {
      setIsLoading(false);
    }
  }, [endpoint, offset, search, formId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Reset offset when form changes
  useEffect(() => {
    setOffset(0);
  }, [formId]);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return {
    data,
    count,
    isLoading,
    search,
    setSearch: (val) => {
      setSearch(val);
      setOffset(0);
    },
    currentPage,
    totalPages,
    canPrev: offset > 0,
    canNext: offset + PAGE_SIZE < count,
    goNext: () => setOffset((o) => o + PAGE_SIZE),
    goPrev: () => setOffset((o) => Math.max(0, o - PAGE_SIZE)),
  };
}

function PaginationControls({
  currentPage,
  totalPages,
  canPrev,
  canNext,
  goNext,
  goPrev,
}) {
  return (
    <div className="flex items-center justify-end gap-2 pt-4">
      <span className="text-sm text-muted-foreground">
        Page {currentPage} of {totalPages}
      </span>
      <Button variant="outline" size="sm" disabled={!canPrev} onClick={goPrev}>
        <ChevronLeft className="size-4" />
      </Button>
      <Button variant="outline" size="sm" disabled={!canNext} onClick={goNext}>
        <ChevronRight className="size-4" />
      </Button>
    </div>
  );
}

function SearchInput({ value, onChange, placeholder }) {
  return (
    <div className="relative max-w-sm">
      <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        type="search"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="pl-8"
      />
    </div>
  );
}

function FarmersTable({ farmers }) {
  if (farmers.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No farmers found.
      </p>
    );
  }

  const valueKeys =
    farmers.length > 0 ? Object.keys(farmers[0].values || {}) : [];

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Farmer ID</TableHead>
            {/* <TableHead>Name</TableHead> */}
            {valueKeys.map((key) => (
              <TableHead key={key} className="capitalize">
                {key.replace(/_/g, " ")}
              </TableHead>
            ))}
            <TableHead className="text-right">Plots</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {farmers.map((farmer) => (
            <TableRow key={farmer.uid}>
              <TableCell className="font-mono text-xs">
                {farmer.farmer_id}
              </TableCell>
              {/* <TableCell className="font-medium">{farmer.name}</TableCell> */}
              {valueKeys.map((key) => (
                <TableCell key={key}>{farmer.values?.[key] ?? ""}</TableCell>
              ))}
              <TableCell className="text-right">{farmer.plot_count}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function EnumeratorsTable({ enumerators }) {
  if (enumerators.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No enumerators found.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Code</TableHead>
            <TableHead>Name</TableHead>
            <TableHead className="text-right">Submissions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {enumerators.map((e) => (
            <TableRow key={e.code}>
              <TableCell className="font-mono text-xs">{e.code}</TableCell>
              <TableCell className="font-medium">{e.name}</TableCell>
              <TableCell className="text-right">{e.submission_count}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function SkeletonTable() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

export default function FarmersAndEnumeratorsPage() {
  const { forms, activeForm, setActiveForm } = useForms();
  const { setSelectedPlotId } = useMapState();
  const [activeTab, setActiveTab] = useState("farmers");

  const formId = activeForm?.asset_uid || "";

  const farmers = usePaginatedData("/v1/odk/farmers/", formId);
  const enumerators = usePaginatedData("/v1/odk/enumerators/", formId);

  const active = activeTab === "farmers" ? farmers : enumerators;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Farmers & Enumerators</h1>
        <p className="text-sm text-muted-foreground">
          View and search registered farmers and enumerators
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>
                {activeTab === "farmers" ? "Farmers" : "Enumerators"}
              </CardTitle>
              <CardDescription>
                {active.count}{" "}
                {activeTab === "farmers" ? "farmer" : "enumerator"}
                {active.count !== 1 ? "s" : ""} found
              </CardDescription>
            </div>
            <div className="flex items-center gap-3">
              <Select
                value={formId}
                onValueChange={(val) => {
                  const form = forms.find((f) => f.asset_uid === val);
                  if (form) {
                    setSelectedPlotId(null);
                    setActiveForm(form);
                  }
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select form" />
                </SelectTrigger>
                <SelectContent>
                  {forms.map((form) => (
                    <SelectItem key={form.asset_uid} value={form.asset_uid}>
                      {form.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList>
                  <TabsTrigger value="farmers">Farmers</TabsTrigger>
                  <TabsTrigger value="enumerators">Enumerators</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <SearchInput
              value={active.search}
              onChange={active.setSearch}
              placeholder={
                activeTab === "farmers"
                  ? "Search by farmer name..."
                  : "Search by enumerator name..."
              }
            />

            {active.isLoading ? (
              <SkeletonTable />
            ) : activeTab === "farmers" ? (
              <FarmersTable farmers={active.data} />
            ) : (
              <EnumeratorsTable enumerators={active.data} />
            )}

            {!active.isLoading && active.count > PAGE_SIZE && (
              <PaginationControls
                currentPage={active.currentPage}
                totalPages={active.totalPages}
                canPrev={active.canPrev}
                canNext={active.canNext}
                goNext={active.goNext}
                goPrev={active.goPrev}
              />
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
