import type { TripStatus } from "../types";

const LABELS: Record<string, string> = {
  queued: "Queued",
  running: "Planning",
  completed: "Ready",
  failed: "Needs attention",
  confirmed: "Confirmed",
  cancelled: "Cancelled",
};

export default function StatusBadge({ status }: { status: TripStatus | "confirmed" | "cancelled" }) {
  return <span className={`badge badge-${status}`}>{LABELS[status] ?? status}</span>;
}
