"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { PageContainer } from "@/components/page-container";
import { jobs as jobsApi, ats as atsApi, type JobSummary, type ATSResult } from "@/lib/api";
import { isApiError } from "@/lib/auth-store";
import { UploadCloud, FileCheck2, Loader2, Search, CheckCircle2, XCircle, Lightbulb, X } from "lucide-react";

function scoreColor(score: number): string {
  if (score >= 75) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 50) return "text-amber-600 dark:text-amber-400";
  return "text-destructive";
}

function ATSPageInner() {
  const searchParams = useSearchParams();

  const [file, setFile] = useState<File | null>(null);
  const [jobQuery, setJobQuery] = useState("");
  const [jobResults, setJobResults] = useState<JobSummary[]>([]);
  const [selectedJob, setSelectedJob] = useState<JobSummary | null>(null);
  const [searching, setSearching] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<ATSResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const prefillJobId = searchParams.get("job_id");

  useEffect(() => {
    if (prefillJobId) {
      jobsApi.get(prefillJobId).then((j) =>
        setSelectedJob({
          id: j.id, title: j.title, company: j.company, location: j.location,
          country: j.country, remote_type: j.remote_type, salary_min: j.salary_min,
          salary_max: j.salary_max, posted_at: j.posted_at, source: j.source,
        })
      ).catch(() => {});
    }
  }, [prefillJobId]);

  const searchJobs = useCallback(() => {
    if (!jobQuery.trim()) return;
    setSearching(true);
    jobsApi.list({ q: jobQuery, limit: 8 }).then((res) => setJobResults(res.jobs)).finally(() => setSearching(false));
  }, [jobQuery]);

  async function handleAnalyze() {
    if (!file || !selectedJob) return;
    setAnalyzing(true);
    setError(null);
    setResult(null);
    try {
      const res = await atsApi.analyze(file, selectedJob.id);
      setResult(res);
    } catch (err) {
      setError(isApiError(err) ? err.message : "Analysis failed. Try a different file.");
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <PageContainer className="max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight">ATS Resume Score</h1>
        <p className="mt-1 text-muted-foreground">
          Upload your resume and pick a job — get a 0–100 score with a full breakdown and specific suggestions.
        </p>
      </div>

      <div className="flex flex-col gap-5">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">1. Your resume</CardTitle>
            <CardDescription>PDF or DOCX, max 5MB</CardDescription>
          </CardHeader>
          <CardContent>
            <label
              htmlFor="resume-file"
              className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors hover:border-primary/50 hover:bg-secondary/30"
            >
              <UploadCloud className="h-7 w-7 text-muted-foreground" />
              {file ? (
                <span className="text-sm font-medium">{file.name}</span>
              ) : (
                <span className="text-sm text-muted-foreground">Click to choose a file, or drag it here</span>
              )}
              <Input
                id="resume-file"
                type="file"
                accept=".pdf,.docx,.doc"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">2. Target job</CardTitle>
            <CardDescription>Search for the job you want to score against</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {selectedJob ? (
              <div className="flex items-center justify-between rounded-lg border bg-secondary/30 px-3 py-2">
                <div>
                  <div className="text-sm font-medium">{selectedJob.title}</div>
                  <div className="text-xs text-muted-foreground">{selectedJob.company}</div>
                </div>
                <Button variant="ghost" size="icon" onClick={() => setSelectedJob(null)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      value={jobQuery}
                      onChange={(e) => setJobQuery(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), searchJobs())}
                      placeholder="e.g. Data Scientist, Backend Engineer..."
                      className="pl-9"
                    />
                  </div>
                  <Button type="button" onClick={searchJobs} disabled={searching}>
                    {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : "Search"}
                  </Button>
                </div>
                {jobResults.length > 0 && (
                  <div className="flex flex-col divide-y rounded-lg border">
                    {jobResults.map((j) => (
                      <button
                        key={j.id}
                        onClick={() => { setSelectedJob(j); setJobResults([]); setJobQuery(""); }}
                        className="flex flex-col items-start gap-0.5 px-3 py-2 text-left text-sm hover:bg-secondary/50"
                      >
                        <span className="font-medium">{j.title}</span>
                        <span className="text-xs text-muted-foreground">{j.company} · {j.location}</span>
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <Button size="lg" onClick={handleAnalyze} disabled={!file || !selectedJob || analyzing}>
          {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileCheck2 className="h-4 w-4" />}
          {analyzing ? "Analyzing..." : "Analyze my resume"}
        </Button>

        {error && (
          <Card className="border-destructive/40 bg-destructive/5">
            <CardContent className="py-4 text-center text-sm text-destructive">{error}</CardContent>
          </Card>
        )}

        {result && (
          <div className="flex flex-col gap-5">
            <Card>
              <CardContent className="flex flex-col items-center gap-2 py-8">
                <div className={`text-6xl font-bold ${scoreColor(result.overall_score)}`}>
                  {Math.round(result.overall_score)}
                </div>
                <div className="text-muted-foreground">out of 100</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="text-base">Score breakdown</CardTitle></CardHeader>
              <CardContent className="flex flex-col gap-4">
                {[
                  { label: "Skill match", value: result.breakdown.skill_match, max: 40 },
                  { label: "Semantic similarity", value: result.breakdown.embedding_sim, max: 30 },
                  { label: "Resume structure", value: result.breakdown.structural, max: 20 },
                  { label: "Keyword overlap", value: result.breakdown.keyword, max: 10 },
                ].map((b) => (
                  <div key={b.label}>
                    <div className="mb-1 flex justify-between text-sm">
                      <span>{b.label}</span>
                      <span className="text-muted-foreground">{b.value.toFixed(1)} / {b.max}</span>
                    </div>
                    <Progress value={(b.value / b.max) * 100} />
                  </div>
                ))}
              </CardContent>
            </Card>

            <div className="grid gap-5 sm:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-1.5 text-base">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" /> Matched skills
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-1.5">
                  {result.matched_skills.length === 0 ? (
                    <span className="text-sm text-muted-foreground">None found</span>
                  ) : result.matched_skills.map((s) => <Badge key={s}>{s}</Badge>)}
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-1.5 text-base">
                    <XCircle className="h-4 w-4 text-destructive" /> Missing skills
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-1.5">
                  {result.missing_skills.length === 0 ? (
                    <span className="text-sm text-muted-foreground">None — great match!</span>
                  ) : result.missing_skills.map((s) => <Badge key={s} variant="destructive">{s}</Badge>)}
                </CardContent>
              </Card>
            </div>

            {result.suggestions.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-1.5 text-base">
                    <Lightbulb className="h-4 w-4 text-amber-500" /> Suggestions
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="flex flex-col gap-2 text-sm">
                    {result.suggestions.map((s, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-muted-foreground">•</span>
                        <span>{s}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </PageContainer>
  );
}

export default function ATSPage() {
  return (
    <Suspense fallback={null}>
      <ATSPageInner />
    </Suspense>
  );
}
