"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button, buttonVariants } from "@/components/ui/button";
import { ButtonLink } from "@/components/button-link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/page-container";
import { jobs as jobsApi, applications as applicationsApi, type JobDetail } from "@/lib/api";
import { useAuthStore, isApiError } from "@/lib/auth-store";
import { formatSalary, formatDate, remoteLabel } from "@/lib/format";
import { ArrowLeft, Building2, MapPin, ExternalLink, Bookmark, FileCheck2, CheckCircle2 } from "lucide-react";

export default function JobDetailPage(props: PageProps<"/jobs/[id]">) {
  const { id } = use(props.params);
  const router = useRouter();
  const { token } = useAuthStore();

  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    jobsApi
      .get(id)
      .then(setJob)
      .catch(() => setError("Job not found."))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleSave() {
    if (!token) {
      toast.message("Log in to save jobs", { description: "You need an account to track applications." });
      router.push("/login");
      return;
    }
    setSaving(true);
    try {
      await applicationsApi.save(id);
      setSaved(true);
      toast.success("Saved to your tracker");
    } catch (err) {
      toast.error(isApiError(err) ? err.message : "Could not save job");
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageContainer className="max-w-4xl">
      <Link href="/jobs" className="mb-6 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Back to jobs
      </Link>

      {loading && (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {error && (
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="py-10 text-center text-destructive">{error}</CardContent>
        </Card>
      )}

      {job && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">{job.title}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-muted-foreground">
                {job.company && <span className="flex items-center gap-1.5"><Building2 className="h-4 w-4" />{job.company}</span>}
                {job.location && <span className="flex items-center gap-1.5"><MapPin className="h-4 w-4" />{job.location}</span>}
              </div>
            </div>
            <div className="text-right">
              <div className="text-lg font-semibold">{formatSalary(job.salary_min, job.salary_max)}</div>
              <div className="text-sm text-muted-foreground">{formatDate(job.posted_at)}</div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-1.5">
            {job.remote_type && <Badge variant="secondary">{remoteLabel(job.remote_type)}</Badge>}
            {job.country && <Badge variant="outline">{job.country}</Badge>}
            <Badge variant="outline" className="capitalize">via {job.source}</Badge>
          </div>

          <div className="mt-6 flex flex-wrap gap-2">
            <Button onClick={handleSave} disabled={saving || saved} variant={saved ? "secondary" : "default"}>
              {saved ? <CheckCircle2 className="h-4 w-4" /> : <Bookmark className="h-4 w-4" />}
              {saved ? "Saved" : "Save to tracker"}
            </Button>
            <ButtonLink href={`/ats?job_id=${job.id}`} variant="outline">
              <FileCheck2 className="h-4 w-4" /> Check my ATS score
            </ButtonLink>
            {job.url && (
              <a
                href={job.url}
                target="_blank"
                rel="noopener noreferrer"
                className={buttonVariants({ variant: "ghost" })}
              >
                Original posting <ExternalLink className="h-4 w-4" />
              </a>
            )}
          </div>

          {(job.required_skills.length > 0 || job.preferred_skills.length > 0) && (
            <Card className="mt-6">
              <CardContent className="flex flex-col gap-3 py-2">
                {job.required_skills.length > 0 && (
                  <div>
                    <div className="mb-1.5 text-sm font-medium">Required skills</div>
                    <div className="flex flex-wrap gap-1.5">
                      {job.required_skills.map((s) => <Badge key={s}>{s}</Badge>)}
                    </div>
                  </div>
                )}
                {job.preferred_skills.length > 0 && (
                  <div>
                    <div className="mb-1.5 text-sm font-medium">Preferred skills</div>
                    <div className="flex flex-wrap gap-1.5">
                      {job.preferred_skills.map((s) => <Badge key={s} variant="secondary">{s}</Badge>)}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {job.description && (
            <Card className="mt-6">
              <CardContent className="prose prose-sm max-w-none whitespace-pre-wrap py-2 text-sm leading-relaxed">
                {job.description}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </PageContainer>
  );
}
