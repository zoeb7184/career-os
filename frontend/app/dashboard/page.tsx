"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { buttonVariants } from "@/components/ui/button";
import { ButtonLink } from "@/components/button-link";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/page-container";
import { RequireAuth } from "@/components/require-auth";
import { cn } from "@/lib/utils";
import {
  applications as applicationsApi, recommend as recommendApi, resumes as resumesApi,
  type Application, type Recommendation,
} from "@/lib/api";
import { useAuthStore, isApiError } from "@/lib/auth-store";
import { formatSalary, formatDate } from "@/lib/format";
import {
  UploadCloud, Loader2, Kanban, Sparkles, Building2, MapPin, ArrowRight,
  Clock, Trophy, Bookmark,
} from "lucide-react";

const STATUS_META: Record<string, { label: string; icon: typeof Clock }> = {
  saved: { label: "Saved", icon: Bookmark },
  applied: { label: "Applied", icon: Clock },
  interview: { label: "Interview", icon: Clock },
  offer: { label: "Offer", icon: Trophy },
  rejected: { label: "Rejected", icon: Clock },
};

function DashboardInner() {
  const { userId, email } = useAuthStore();
  const [apps, setApps] = useState<Application[] | null>(null);
  const [recs, setRecs] = useState<Recommendation[] | null>(null);
  const [needsResume, setNeedsResume] = useState(false);
  const [uploading, setUploading] = useState(false);

  const loadRecs = useCallback(() => {
    if (!userId) return;
    setNeedsResume(false);
    setRecs(null);
    recommendApi
      .forUser(userId, { top_n: 6 })
      .then((res) => setRecs(res.recommendations))
      .catch((err) => {
        if (isApiError(err) && err.status === 404) {
          setNeedsResume(true);
          setRecs([]);
        } else {
          setRecs([]);
        }
      });
  }, [userId]);

  useEffect(() => {
    applicationsApi.list().then(setApps).catch(() => setApps([]));
    loadRecs();
  }, [loadRecs]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await resumesApi.upload(file);
      toast.success("Resume uploaded — generating recommendations...");
      // embedding + skill extraction run async in the worker; give it a moment
      setTimeout(loadRecs, 4000);
    } catch (err) {
      toast.error(isApiError(err) ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  const counts = apps?.reduce<Record<string, number>>((acc, a) => {
    acc[a.status] = (acc[a.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <PageContainer>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">Welcome back{email ? `, ${email.split("@")[0]}` : ""}</h1>
        <p className="mt-1 text-muted-foreground">Your job search at a glance.</p>
      </div>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {(["saved", "applied", "interview", "offer", "rejected"] as const).map((s) => {
          const Meta = STATUS_META[s];
          return (
            <Card key={s}>
              <CardContent className="flex items-center gap-3 py-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
                  <Meta.icon className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-xl font-bold tabular-nums">{apps ? counts?.[s] ?? 0 : <Skeleton className="h-5 w-5" />}</div>
                  <div className="text-xs text-muted-foreground">{Meta.label}</div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-1.5 text-base"><Sparkles className="h-4 w-4" /> Recommended for you</CardTitle>
                <CardDescription>Based on your uploaded resume</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {needsResume && (
                <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed p-8 text-center">
                  <UploadCloud className="h-8 w-8 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">
                    Upload a resume to get personalised job recommendations.
                  </p>
                  <label className={cn(buttonVariants(), "cursor-pointer", uploading && "pointer-events-none opacity-50")}>
                    {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                    Upload resume
                    <Input type="file" accept=".pdf,.docx,.doc" className="hidden" onChange={handleUpload} disabled={uploading} />
                  </label>
                </div>
              )}

              {!needsResume && recs === null && (
                <div className="flex flex-col gap-3">
                  {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}
                </div>
              )}

              {!needsResume && recs !== null && recs.length === 0 && (
                <div className="py-10 text-center text-sm text-muted-foreground">
                  No recommendations yet — check back once your resume finishes processing.
                </div>
              )}

              {!needsResume && recs && recs.length > 0 && (
                <div className="flex flex-col gap-3">
                  {recs.map((r) => (
                    <Link key={r.job_id} href={`/jobs/${r.job_id}`}>
                      <div className="flex items-center justify-between rounded-lg border px-4 py-3 transition-colors hover:border-primary/50">
                        <div>
                          <div className="font-medium">{r.title}</div>
                          <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                            {r.company && <span className="flex items-center gap-1"><Building2 className="h-3 w-3" />{r.company}</span>}
                            {r.location && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{r.location}</span>}
                          </div>
                        </div>
                        <div className="text-right">
                          <Badge variant="secondary">{Math.round(r.final_score * 100)}% match</Badge>
                          <div className="mt-1 text-xs text-muted-foreground">{formatSalary(r.salary_min, r.salary_max)}</div>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5 text-base"><Kanban className="h-4 w-4" /> Recent applications</CardTitle>
            </CardHeader>
            <CardContent>
              {apps === null && <div className="flex flex-col gap-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>}
              {apps && apps.length === 0 && (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  No saved jobs yet. <Link href="/jobs" className="text-primary hover:underline">Browse jobs</Link>
                </div>
              )}
              {apps && apps.length > 0 && (
                <div className="flex flex-col divide-y">
                  {apps.slice(0, 6).map((a) => (
                    <div key={a.id} className="flex items-center justify-between py-2.5">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">{a.job.title ?? "Untitled role"}</div>
                        <div className="text-xs text-muted-foreground">{a.job.company}</div>
                      </div>
                      <Badge variant="outline" className="capitalize shrink-0">{a.status}</Badge>
                    </div>
                  ))}
                </div>
              )}
              <ButtonLink href="/tracker" variant="ghost" size="sm" className="mt-3 w-full">
                Open tracker <ArrowRight className="h-3.5 w-3.5" />
              </ButtonLink>
            </CardContent>
          </Card>
        </div>
      </div>
    </PageContainer>
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardInner />
    </RequireAuth>
  );
}
