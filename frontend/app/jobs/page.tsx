"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/page-container";
import { jobs as jobsApi, type JobSummary } from "@/lib/api";
import { formatSalary, formatDate, remoteLabel } from "@/lib/format";
import { Search, MapPin, Building2, ChevronLeft, ChevronRight, Briefcase } from "lucide-react";

const COUNTRIES = [
  { value: "all", label: "All countries" },
  { value: "DE", label: "Germany" },
  { value: "GB", label: "United Kingdom" },
];

const REMOTE_TYPES = [
  { value: "all", label: "Any work type" },
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "Onsite" },
];

function JobsPageInner() {
  const searchParams = useSearchParams();

  const [q, setQ] = useState(searchParams.get("q") ?? "");
  const [country, setCountry] = useState(searchParams.get("country") ?? "all");
  const [remoteType, setRemoteType] = useState(searchParams.get("remote_type") ?? "all");
  const [page, setPage] = useState(Number(searchParams.get("page") ?? "1"));

  const [data, setData] = useState<{ jobs: JobSummary[]; total: number; pages: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = useCallback(() => {
    setLoading(true);
    setError(null);
    jobsApi
      .list({
        q: q || undefined,
        country: country !== "all" ? country : undefined,
        remote_type: remoteType !== "all" ? remoteType : undefined,
        page,
        limit: 20,
      })
      .then((res) => setData(res))
      .catch(() => setError("Could not load jobs. Is the backend running?"))
      .finally(() => setLoading(false));
  }, [q, country, remoteType, page]);

  useEffect(() => {
    fetchJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, country, remoteType]);

  function onSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    fetchJobs();
  }

  return (
    <PageContainer>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Job search</h1>
        <p className="mt-1 text-muted-foreground">
          {data ? `${data.total.toLocaleString()} active listings` : "Live listings from Adzuna, Reed, and Remotive"}
        </p>
      </div>

      <form onSubmit={onSearchSubmit} className="mb-6 flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search title or description — e.g. Data Scientist, Python..."
            className="pl-9"
          />
        </div>
        <Select value={country} onValueChange={(v) => { if (v) { setCountry(v); setPage(1); } }}>
          <SelectTrigger className="sm:w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            {COUNTRIES.map((c) => <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={remoteType} onValueChange={(v) => { if (v) { setRemoteType(v); setPage(1); } }}>
          <SelectTrigger className="sm:w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            {REMOTE_TYPES.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button type="submit">Search</Button>
      </form>

      {error && (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="py-6 text-center text-sm text-destructive">{error}</CardContent>
        </Card>
      )}

      {loading && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-28 w-full" />)}
        </div>
      )}

      {!loading && !error && data && (
        <>
          {data.jobs.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-2 py-16 text-center text-muted-foreground">
                <Briefcase className="h-8 w-8" />
                <p>No jobs match your filters. Try broadening your search.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="flex flex-col gap-3">
              {data.jobs.map((job) => (
                <Link key={job.id} href={`/jobs/${job.id}`}>
                  <Card className="transition-colors hover:border-primary/50">
                    <CardContent className="flex flex-col gap-2 py-1">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <h3 className="font-semibold leading-snug">{job.title}</h3>
                          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
                            {job.company && (
                              <span className="flex items-center gap-1"><Building2 className="h-3.5 w-3.5" />{job.company}</span>
                            )}
                            {job.location && (
                              <span className="flex items-center gap-1"><MapPin className="h-3.5 w-3.5" />{job.location}</span>
                            )}
                          </div>
                        </div>
                        <div className="text-right text-sm">
                          <div className="font-medium">{formatSalary(job.salary_min, job.salary_max)}</div>
                          <div className="text-muted-foreground">{formatDate(job.posted_at)}</div>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5">
                        {job.remote_type && <Badge variant="secondary">{remoteLabel(job.remote_type)}</Badge>}
                        {job.country && <Badge variant="outline">{job.country}</Badge>}
                        <Badge variant="outline" className="capitalize">{job.source}</Badge>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}

          {data.pages > 1 && (
            <div className="mt-6 flex items-center justify-center gap-3">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                <ChevronLeft className="h-4 w-4" /> Prev
              </Button>
              <span className="text-sm text-muted-foreground">Page {page} of {data.pages}</span>
              <Button variant="outline" size="sm" disabled={page >= data.pages} onClick={() => setPage((p) => p + 1)}>
                Next <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </PageContainer>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={null}>
      <JobsPageInner />
    </Suspense>
  );
}
