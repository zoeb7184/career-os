"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@/components/ui/table";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/page-container";
import { RequireAuth } from "@/components/require-auth";
import { cn } from "@/lib/utils";
import { formatSalary } from "@/lib/format";
import {
  imports as importsApi, applications as applicationsApi,
  type ImportPreview, type ImportRow, type ImportHistoryEntry,
  type Application, type ApplicationStatus,
} from "@/lib/api";
import { isApiError } from "@/lib/auth-store";
import {
  Sparkles, UploadCloud, FileSpreadsheet, FileText, Loader2, X,
  AlertTriangle, CheckCircle2, Search, Download, MoreHorizontal, Trash2,
  Building2, MapPin, ArrowUpDown, History, ExternalLink,
} from "lucide-react";

// ── Shared helpers ──────────────────────────────────────────────────

const STATUS_META: Record<ApplicationStatus, { label: string; className: string }> = {
  saved:     { label: "Saved",     className: "bg-muted text-muted-foreground" },
  applied:   { label: "Applied",   className: "bg-[color-mix(in_oklch,var(--status-warning)_16%,transparent)] text-[color:var(--status-warning)]" },
  interview: { label: "Interview", className: "bg-primary/10 text-primary" },
  offer:     { label: "Offer",     className: "bg-brand/15 text-brand" },
  rejected:  { label: "Rejected",  className: "bg-destructive/10 text-destructive" },
};

function StatusBadge({ status }: { status: ApplicationStatus }) {
  const meta = STATUS_META[status] ?? STATUS_META.applied;
  return <Badge className={cn("border-transparent capitalize", meta.className)}>{meta.label}</Badge>;
}

function daysSince(iso: string | null): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return Math.max(0, Math.floor((Date.now() - d.getTime()) / 86_400_000));
}

const STALE_DAYS = 30;

function isStaleApp(a: Application): boolean {
  const days = daysSince(a.applied_at ?? a.created_at);
  return a.status === "applied" && days !== null && days >= STALE_DAYS;
}

function csvEscape(v: string | number | null | undefined): string {
  const s = v == null ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function exportCsv(rows: Application[]) {
  const header = [
    "Job Title", "Company", "Location", "Status", "Applied Date", "Days Since Applied",
    "Platform", "Job URL", "Notes", "Salary Min", "Salary Max",
  ];
  const lines = [header.join(",")];
  for (const a of rows) {
    lines.push([
      a.job.title, a.job.company, a.job.location, a.status,
      a.applied_at, daysSince(a.applied_at ?? a.created_at),
      a.platform, a.job.url, a.notes, a.job.salary_min, a.job.salary_max,
    ].map(csvEscape).join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `career-os-applications-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

const COLUMN_LABELS: Record<string, string> = {
  job_title: "Job Title", company: "Company", location: "Location",
  date_applied: "Date Applied", status: "Status", job_url: "Job URL",
  notes: "Notes", salary: "Salary", platform: "Source / Platform",
};

// ── Upload zone ──────────────────────────────────────────────────────

function UploadZone({ uploading, onFile }: { uploading: boolean; onFile: (f: File) => void }) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      onClick={() => !uploading && inputRef.current?.click()}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-12 text-center transition-colors",
        dragOver ? "border-brand bg-brand/5" : "hover:border-primary/50 hover:bg-secondary/30",
        uploading && "pointer-events-none opacity-60"
      )}
    >
      {uploading ? (
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      ) : (
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-brand/10 text-brand">
          <UploadCloud className="h-7 w-7" />
        </div>
      )}
      <div>
        <p className="font-medium">
          {uploading ? "Parsing your file..." : "Drag & drop your application tracker here"}
        </p>
        {!uploading && (
          <p className="mt-1 text-sm text-muted-foreground">
            or click to browse — accepts <span className="font-medium">.xlsx</span> or <span className="font-medium">.pdf</span>
          </p>
        )}
      </div>
      <Input
        ref={inputRef}
        type="file"
        accept=".xlsx,.pdf"
        className="hidden"
        disabled={uploading}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
    </div>
  );
}

// ── Import wizard ────────────────────────────────────────────────────

function ImportWizard({ onImported }: { onImported: () => void }) {
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [confirming, setConfirming] = useState(false);

  async function handleFile(file: File) {
    const ext = file.name.toLowerCase().split(".").pop();
    if (ext !== "xlsx" && ext !== "pdf") {
      toast.error("Only .xlsx or .pdf files are supported.");
      return;
    }
    setUploading(true);
    try {
      const res = await importsApi.upload(file);
      setPreview(res);
      if (res.summary.total === 0) {
        toast.warning("No rows were detected in that file.");
      }
    } catch (err) {
      toast.error(isApiError(err) ? err.message : "Could not parse that file.");
    } finally {
      setUploading(false);
    }
  }

  function updateRow(index: number, patch: Partial<ImportRow>) {
    setPreview((prev) => {
      if (!prev) return prev;
      const rows = prev.rows.slice();
      rows[index] = { ...rows[index], ...patch };
      return { ...prev, rows };
    });
  }

  async function handleConfirm() {
    if (!preview) return;
    setConfirming(true);
    try {
      const res = await importsApi.confirm(preview.filename, preview.file_type, preview.rows);
      toast.success(
        `Imported ${res.imported} application${res.imported === 1 ? "" : "s"}` +
        (res.skipped ? ` — skipped ${res.skipped}` : "")
      );
      setPreview(null);
      onImported();
    } catch (err) {
      toast.error(isApiError(err) ? err.message : "Import failed");
    } finally {
      setConfirming(false);
    }
  }

  if (!preview) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-1.5 text-base">
            <Sparkles className="h-4 w-4 text-brand" /> Upload your applications
          </CardTitle>
          <CardDescription>
            Export your tracker from Excel, Notion, or Google Sheets as .xlsx (best results) or .pdf, then drop it here.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <UploadZone uploading={uploading} onFile={handleFile} />
        </CardContent>
      </Card>
    );
  }

  const includedCount = preview.rows.filter((r) => !r.skip).length;
  const { summary } = preview;

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle className="flex items-center gap-1.5 text-base">
              {preview.file_type === "pdf" ? <FileText className="h-4 w-4" /> : <FileSpreadsheet className="h-4 w-4" />}
              {preview.filename}
            </CardTitle>
            <CardDescription>
              {summary.total} job{summary.total === 1 ? "" : "s"} found — {summary.applied} applied, {summary.interview} interview{summary.interview === 1 ? "" : "s"}, {summary.offer} offer{summary.offer === 1 ? "" : "s"}, {summary.rejected} rejected
              {summary.saved > 0 ? `, ${summary.saved} saved` : ""}
            </CardDescription>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setPreview(null)}>
            <X className="h-4 w-4" /> Start over
          </Button>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {/* Detected column mapping */}
          <div className="flex flex-wrap items-center gap-1.5 rounded-lg border bg-secondary/20 px-3 py-2.5 text-xs">
            <span className="mr-1 font-medium text-muted-foreground">Detected columns:</span>
            {Object.entries(preview.column_mapping).map(([field, col]) => (
              <Badge key={field} variant={col ? "secondary" : "outline"} className={cn(!col && "text-muted-foreground/60")}>
                {COLUMN_LABELS[field] ?? field}{col ? ` ← "${col}"` : " — not found"}
              </Badge>
            ))}
          </div>

          {/* Quick stats */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile label="Duplicates found" value={summary.duplicate_count} tone="warning" />
            <StatTile label="Stale (30+ days)" value={summary.stale_count} tone="warning" />
            <StatTile label="Response rate" value={`${Math.round(summary.response_rate * 100)}%`} tone="brand" />
            <StatTile label="Will be imported" value={includedCount} tone="good" />
          </div>

          {summary.duplicate_count > 0 && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                {summary.duplicate_count} row{summary.duplicate_count === 1 ? "" : "s"} look{summary.duplicate_count === 1 ? "s" : ""} like duplicates
                (either repeated in this file or already in your tracker) — they&apos;re unchecked below by default. Review and tick
                the box to import anyway.
              </span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Review before importing</CardTitle>
          <CardDescription>Fix any misdetected values inline, then confirm.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="max-h-[32rem] overflow-y-auto">
            <Table>
              <TableHeader className="sticky top-0 z-10 bg-card">
                <TableRow>
                  <TableHead className="w-8"></TableHead>
                  <TableHead className="min-w-40">Job title</TableHead>
                  <TableHead className="min-w-36">Company</TableHead>
                  <TableHead className="min-w-32">Location</TableHead>
                  <TableHead className="min-w-32">Date applied</TableHead>
                  <TableHead className="min-w-32">Status</TableHead>
                  <TableHead className="min-w-32">Platform</TableHead>
                  <TableHead>Flags</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {preview.rows.map((row, i) => (
                  <TableRow
                    key={row.row_index}
                    className={cn(row.is_duplicate && "bg-destructive/5", row.skip && "opacity-60")}
                  >
                    <TableCell>
                      <Checkbox
                        checked={!row.skip}
                        onCheckedChange={(checked) => updateRow(i, { skip: checked !== true })}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        value={row.job_title ?? ""}
                        onChange={(e) => updateRow(i, { job_title: e.target.value })}
                        className="h-8 min-w-40"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        value={row.company ?? ""}
                        onChange={(e) => updateRow(i, { company: e.target.value })}
                        className="h-8 min-w-32"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        value={row.location ?? ""}
                        onChange={(e) => updateRow(i, { location: e.target.value })}
                        className="h-8 min-w-28"
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="date"
                        value={row.date_applied ?? ""}
                        onChange={(e) => updateRow(i, { date_applied: e.target.value || null })}
                        className="h-8 min-w-32"
                      />
                    </TableCell>
                    <TableCell>
                      <Select
                        value={row.status}
                        onValueChange={(v) => v && updateRow(i, { status: v as ApplicationStatus })}
                      >
                        <SelectTrigger className="h-8 w-32"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {(Object.keys(STATUS_META) as ApplicationStatus[]).map((s) => (
                            <SelectItem key={s} value={s}>{STATUS_META[s].label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Input
                        value={row.platform ?? ""}
                        onChange={(e) => updateRow(i, { platform: e.target.value })}
                        className="h-8 min-w-28"
                      />
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {row.is_duplicate && (
                          <Badge variant="destructive" className="text-[10px]">
                            {row.duplicate_reason ?? "Duplicate"}
                          </Badge>
                        )}
                        {row.is_stale && <Badge variant="outline" className="text-[10px]">Stale</Badge>}
                        {!row.status_recognized && (
                          <Badge variant="outline" className="text-[10px] text-muted-foreground">Status guessed</Badge>
                        )}
                        {row.warnings.map((w, wi) => (
                          <Badge key={wi} variant="outline" className="text-[10px] text-muted-foreground">{w}</Badge>
                        ))}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Button variant="outline" onClick={() => setPreview(null)} disabled={confirming}>Cancel</Button>
        <Button size="lg" onClick={handleConfirm} disabled={confirming || includedCount === 0}>
          {confirming ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
          {confirming ? "Importing..." : `Import ${includedCount} application${includedCount === 1 ? "" : "s"}`}
        </Button>
      </div>
    </div>
  );
}

function StatTile({ label, value, tone }: { label: string; value: string | number; tone: "warning" | "brand" | "good" }) {
  const toneClass = {
    warning: "text-[color:var(--status-warning)]",
    brand: "text-brand",
    good: "text-[color:var(--status-good)]",
  }[tone];
  return (
    <div className="rounded-lg border px-3 py-2.5">
      <div className={cn("text-xl font-bold tabular-nums", toneClass)}>{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

// ── Post-import enhanced table view ─────────────────────────────────

type SortKey = "title" | "company" | "status" | "applied" | "days" | "salary";

function SortHead({ label, sortKey, onSort }: { label: string; sortKey: SortKey; onSort: (key: SortKey) => void }) {
  return (
    <TableHead>
      <button onClick={() => onSort(sortKey)} className="flex items-center gap-1 hover:text-foreground">
        {label} <ArrowUpDown className="h-3 w-3 opacity-50" />
      </button>
    </TableHead>
  );
}

function ApplicationsTable({ apps, loading, onChanged }: {
  apps: Application[] | null; loading: boolean; onChanged: () => void;
}) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ApplicationStatus | "all">("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("applied");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("desc"); }
  }

  const filtered = useMemo(() => {
    if (!apps) return [];
    const q = search.trim().toLowerCase();
    let rows = apps.filter((a) => {
      if (statusFilter !== "all" && a.status !== statusFilter) return false;
      if (q) {
        const haystack = `${a.job.title ?? ""} ${a.job.company ?? ""} ${a.job.location ?? ""} ${a.notes ?? ""}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      if (dateFrom && (!a.applied_at || a.applied_at < dateFrom)) return false;
      if (dateTo && (!a.applied_at || a.applied_at > dateTo)) return false;
      return true;
    });

    rows = rows.slice().sort((a, b) => {
      const dir = sortDir === "asc" ? 1 : -1;
      switch (sortKey) {
        case "title": return (a.job.title ?? "").localeCompare(b.job.title ?? "") * dir;
        case "company": return (a.job.company ?? "").localeCompare(b.job.company ?? "") * dir;
        case "status": return a.status.localeCompare(b.status) * dir;
        case "salary": return ((a.job.salary_max ?? a.job.salary_min ?? 0) - (b.job.salary_max ?? b.job.salary_min ?? 0)) * dir;
        case "days": {
          const da = daysSince(a.applied_at ?? a.created_at) ?? -1;
          const db = daysSince(b.applied_at ?? b.created_at) ?? -1;
          return (da - db) * dir;
        }
        case "applied":
        default: {
          const da = a.applied_at ?? a.created_at ?? "";
          const db = b.applied_at ?? b.created_at ?? "";
          return da.localeCompare(db) * dir;
        }
      }
    });
    return rows;
  }, [apps, search, statusFilter, dateFrom, dateTo, sortKey, sortDir]);

  async function handleStatusChange(app: Application, status: ApplicationStatus) {
    try {
      await applicationsApi.updateStatus(app.id, status);
      toast.success(`Marked as ${STATUS_META[status].label.toLowerCase()}`);
      onChanged();
    } catch (err) {
      toast.error(isApiError(err) ? err.message : "Could not update status");
    }
  }

  async function handleDelete(app: Application) {
    try {
      await applicationsApi.remove(app.id);
      toast.success("Removed from tracker");
      onChanged();
    } catch (err) {
      toast.error(isApiError(err) ? err.message : "Could not remove");
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
        <div>
          <CardTitle className="text-base">Your applications</CardTitle>
          <CardDescription>
            {apps ? `${filtered.length} of ${apps.length} shown` : "Loading..."}
          </CardDescription>
        </div>
        <Button variant="outline" size="sm" disabled={!apps || apps.length === 0} onClick={() => apps && exportCsv(filtered)}>
          <Download className="h-4 w-4" /> Export CSV
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
          <div className="relative flex-1 sm:min-w-52">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search title, company, notes..." className="pl-9" />
          </div>
          <Select value={statusFilter} onValueChange={(v) => v && setStatusFilter(v as ApplicationStatus | "all")}>
            <SelectTrigger className="sm:w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              {(Object.keys(STATUS_META) as ApplicationStatus[]).map((s) => (
                <SelectItem key={s} value={s}>{STATUS_META[s].label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex items-center gap-1.5">
            <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="w-36" aria-label="From date" />
            <span className="text-xs text-muted-foreground">to</span>
            <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="w-36" aria-label="To date" />
          </div>
        </div>

        {loading && (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        )}

        {!loading && apps && apps.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-12 text-center text-muted-foreground">
            <FileSpreadsheet className="h-8 w-8" />
            <p>No applications yet. Import a file above, or <Link href="/jobs" className="text-primary hover:underline">browse jobs</Link>.</p>
          </div>
        )}

        {!loading && apps && apps.length > 0 && (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <SortHead label="Job" sortKey="title" onSort={toggleSort} />
                  <SortHead label="Company" sortKey="company" onSort={toggleSort} />
                  <SortHead label="Status" sortKey="status" onSort={toggleSort} />
                  <SortHead label="Applied" sortKey="applied" onSort={toggleSort} />
                  <SortHead label="Days" sortKey="days" onSort={toggleSort} />
                  <SortHead label="Salary" sortKey="salary" onSort={toggleSort} />
                  <TableHead>Source</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((a) => {
                  const days = daysSince(a.applied_at ?? a.created_at);
                  const stale = isStaleApp(a);
                  return (
                    <TableRow key={a.id}>
                      <TableCell className="max-w-52">
                        <div className="flex items-center gap-1.5 truncate font-medium">
                          {a.job.title ?? "Untitled role"}
                          {a.job.url && (
                            <a href={a.job.url} target="_blank" rel="noreferrer" className="text-muted-foreground hover:text-primary">
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </div>
                        {a.job.location && (
                          <div className="flex items-center gap-1 text-xs text-muted-foreground"><MapPin className="h-3 w-3" />{a.job.location}</div>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="flex items-center gap-1"><Building2 className="h-3.5 w-3.5 text-muted-foreground" />{a.job.company ?? "—"}</span>
                      </TableCell>
                      <TableCell><StatusBadge status={a.status} /></TableCell>
                      <TableCell className="text-muted-foreground">{a.applied_at ?? "—"}</TableCell>
                      <TableCell>
                        {days === null ? (
                          <span className="text-muted-foreground">—</span>
                        ) : (
                          <span className={cn("flex items-center gap-1", stale && "text-[color:var(--status-warning)] font-medium")}>
                            {stale && <AlertTriangle className="h-3.5 w-3.5" />}
                            {days}d
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">{formatSalary(a.job.salary_min, a.job.salary_max)}</TableCell>
                      <TableCell className="text-muted-foreground">{a.platform ?? "—"}</TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger className="rounded-md p-1.5 hover:bg-muted">
                            <MoreHorizontal className="h-4 w-4" />
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            {(Object.keys(STATUS_META) as ApplicationStatus[])
                              .filter((s) => s !== a.status)
                              .map((s) => (
                                <DropdownMenuItem key={s} onClick={() => handleStatusChange(a, s)}>
                                  Mark as {STATUS_META[s].label}
                                </DropdownMenuItem>
                              ))}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem variant="destructive" onClick={() => handleDelete(a)}>
                              <Trash2 className="h-3.5 w-3.5" /> Remove
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Import history ───────────────────────────────────────────────────

function ImportHistoryCard({ history }: { history: ImportHistoryEntry[] | null }) {
  if (!history || history.length === 0) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5 text-base"><History className="h-4 w-4" /> Import history</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col divide-y">
        {history.map((h) => (
          <div key={h.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 text-sm">
            <div className="flex items-center gap-2">
              {h.file_type === "pdf" ? <FileText className="h-4 w-4 text-muted-foreground" /> : <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />}
              <span className="font-medium">{h.filename}</span>
              <span className="text-xs text-muted-foreground">{h.created_at ? new Date(h.created_at).toLocaleDateString() : ""}</span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Badge variant="secondary">{h.imported_rows}/{h.total_rows} imported</Badge>
              {h.duplicate_count > 0 && <Badge variant="outline">{h.duplicate_count} dupes</Badge>}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// ── Page ──────────────────────────────────────────────────────────────

function ImportPageInner() {
  const [apps, setApps] = useState<Application[] | null>(null);
  const [loadingApps, setLoadingApps] = useState(true);
  const [history, setHistory] = useState<ImportHistoryEntry[] | null>(null);

  const loadApplications = useCallback(() => {
    setLoadingApps(true);
    applicationsApi.list().then(setApps).catch(() => setApps([])).finally(() => setLoadingApps(false));
  }, []);

  const loadHistory = useCallback(() => {
    importsApi.history().then(setHistory).catch(() => setHistory([]));
  }, []);

  useEffect(() => {
    loadApplications();
    loadHistory();
  }, [loadApplications, loadHistory]);

  function handleImported() {
    loadApplications();
    loadHistory();
  }

  return (
    <PageContainer className="max-w-6xl">
      <div className="mb-8">
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
          <Sparkles className="h-6 w-6 text-brand" /> Smart Import
        </h1>
        <p className="mt-1 text-muted-foreground">
          Bring an existing spreadsheet or PDF tracker into Career OS — we&apos;ll auto-detect columns,
          normalise statuses, and flag duplicates and stale applications before anything is saved.
        </p>
      </div>

      <div className="flex flex-col gap-6">
        <ImportWizard onImported={handleImported} />
        <ImportHistoryCard history={history} />
        <ApplicationsTable apps={apps} loading={loadingApps} onChanged={loadApplications} />
      </div>
    </PageContainer>
  );
}

export default function ImportPage() {
  return (
    <RequireAuth>
      <ImportPageInner />
    </RequireAuth>
  );
}
