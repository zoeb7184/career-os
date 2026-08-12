export function formatSalary(min: number | null, max: number | null, currency = "£"): string {
  if (min == null && max == null) return "Not disclosed";
  const fmt = (n: number) => `${currency}${Math.round(n).toLocaleString()}`;
  if (min != null && max != null) {
    if (min === max) return fmt(min);
    return `${fmt(min)} – ${fmt(max)}`;
  }
  return fmt((min ?? max) as number);
}

export function formatDate(iso: string | null): string {
  if (!iso) return "Unknown date";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Unknown date";
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function remoteLabel(type: string | null): string {
  if (!type) return "Unknown";
  return type.charAt(0).toUpperCase() + type.slice(1);
}

export function initials(email: string | null): string {
  if (!email) return "?";
  return email[0]?.toUpperCase() ?? "?";
}
