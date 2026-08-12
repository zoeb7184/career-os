"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  DndContext, DragOverlay, useDraggable, useDroppable,
  type DragStartEvent, type DragEndEvent, PointerSensor, useSensor, useSensors,
} from "@dnd-kit/core";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/button-link";
import { Skeleton } from "@/components/ui/skeleton";
import { PageContainer } from "@/components/page-container";
import { RequireAuth } from "@/components/require-auth";
import { applications as applicationsApi, type Application, type ApplicationStatus } from "@/lib/api";
import { isApiError } from "@/lib/auth-store";
import { Building2, MapPin, Trash2, GripVertical, Kanban as KanbanIcon } from "lucide-react";
import { cn } from "@/lib/utils";

const COLUMNS: { status: ApplicationStatus; label: string }[] = [
  { status: "saved", label: "Saved" },
  { status: "applied", label: "Applied" },
  { status: "interview", label: "Interview" },
  { status: "offer", label: "Offer" },
  { status: "rejected", label: "Rejected" },
];

function AppCard({ app, onDelete }: { app: Application; onDelete: (id: string) => void }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({ id: app.id });
  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`, zIndex: isDragging ? 50 : undefined }
    : undefined;

  return (
    <div ref={setNodeRef} style={style} className={cn(isDragging && "opacity-50")}>
      <Card className="group">
        <CardContent className="flex items-start gap-2 py-3">
          <button {...listeners} {...attributes} className="mt-0.5 cursor-grab touch-none text-muted-foreground active:cursor-grabbing">
            <GripVertical className="h-4 w-4" />
          </button>
          <div className="min-w-0 flex-1">
            <Link href={`/jobs/${app.job_id}`} className="line-clamp-2 text-sm font-medium hover:underline">
              {app.job.title ?? "Untitled role"}
            </Link>
            <div className="mt-1 flex flex-col gap-0.5 text-xs text-muted-foreground">
              {app.job.company && <span className="flex items-center gap-1"><Building2 className="h-3 w-3" />{app.job.company}</span>}
              {app.job.location && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{app.job.location}</span>}
            </div>
            {app.ats_score != null && (
              <Badge variant="outline" className="mt-2 text-xs">ATS {Math.round(app.ats_score)}</Badge>
            )}
          </div>
          <button
            onClick={() => onDelete(app.id)}
            className="text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </CardContent>
      </Card>
    </div>
  );
}

function Column({ status, label, apps, onDelete }: {
  status: ApplicationStatus; label: string; apps: Application[]; onDelete: (id: string) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex w-72 shrink-0 flex-col rounded-lg border bg-secondary/20 transition-colors",
        isOver && "border-primary/50 bg-primary/5"
      )}
    >
      <div className="flex items-center justify-between border-b px-3 py-2.5">
        <span className="text-sm font-semibold">{label}</span>
        <Badge variant="secondary">{apps.length}</Badge>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-2.5 min-h-24">
        {apps.map((a) => <AppCard key={a.id} app={a} onDelete={onDelete} />)}
        {apps.length === 0 && (
          <div className="flex flex-1 items-center justify-center rounded-md border border-dashed py-8 text-xs text-muted-foreground">
            Drop here
          </div>
        )}
      </div>
    </div>
  );
}

function TrackerInner() {
  const [apps, setApps] = useState<Application[] | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  useEffect(() => {
    applicationsApi.list().then(setApps).catch(() => setApps([]));
  }, []);

  function handleDragStart(e: DragStartEvent) {
    setActiveId(String(e.active.id));
  }

  async function handleDragEnd(e: DragEndEvent) {
    setActiveId(null);
    const { active, over } = e;
    if (!over) return;
    const appId = String(active.id);
    const newStatus = over.id as ApplicationStatus;
    const current = apps?.find((a) => a.id === appId);
    if (!current || current.status === newStatus) return;

    setApps((prev) => prev?.map((a) => (a.id === appId ? { ...a, status: newStatus } : a)) ?? prev);
    try {
      await applicationsApi.updateStatus(appId, newStatus);
    } catch (err) {
      setApps((prev) => prev?.map((a) => (a.id === appId ? { ...a, status: current.status } : a)) ?? prev);
      toast.error(isApiError(err) ? err.message : "Could not update status");
    }
  }

  async function handleDelete(id: string) {
    const prev = apps;
    setApps((p) => p?.filter((a) => a.id !== id) ?? p);
    try {
      await applicationsApi.remove(id);
    } catch (err) {
      setApps(prev);
      toast.error(isApiError(err) ? err.message : "Could not remove");
    }
  }

  const activeApp = apps?.find((a) => a.id === activeId);

  return (
    <PageContainer className="max-w-none">
      <div className="mb-8">
        <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight">
          <KanbanIcon className="h-6 w-6 text-primary" /> Application Tracker
        </h1>
        <p className="mt-1 text-muted-foreground">Drag cards between columns to update status.</p>
      </div>

      {apps === null ? (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {COLUMNS.map((c) => <Skeleton key={c.status} className="h-96 w-72 shrink-0" />)}
        </div>
      ) : apps.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-16 text-center text-muted-foreground">
            <KanbanIcon className="h-8 w-8" />
            <p>No saved jobs yet.</p>
            <ButtonLink href="/jobs">Browse jobs</ButtonLink>
          </CardContent>
        </Card>
      ) : (
        <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
          <div className="flex gap-4 overflow-x-auto pb-4">
            {COLUMNS.map((c) => (
              <Column
                key={c.status}
                status={c.status}
                label={c.label}
                apps={apps.filter((a) => a.status === c.status)}
                onDelete={handleDelete}
              />
            ))}
          </div>
          <DragOverlay>
            {activeApp && (
              <Card className="w-64 rotate-2 shadow-lg">
                <CardContent className="py-3 text-sm font-medium">{activeApp.job.title}</CardContent>
              </Card>
            )}
          </DragOverlay>
        </DndContext>
      )}
    </PageContainer>
  );
}

export default function TrackerPage() {
  return (
    <RequireAuth>
      <TrackerInner />
    </RequireAuth>
  );
}
