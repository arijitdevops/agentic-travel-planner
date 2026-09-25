import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { PLANNING_AGENTS } from "../lib/agents";
import type { TripEvent } from "../types";

interface Props {
  tripId: number;
  onFinished: () => void;
}

type AgentState = "pending" | "running" | "done";

export default function AgentProgress({ tripId, onFinished }: Props) {
  const [events, setEvents] = useState<TripEvent[]>([]);
  const finished = useRef(false);
  const logRef = useRef<HTMLOListElement>(null);

  useEffect(() => {
    finished.current = false;
    const seen = new Set<number>();
    const add = (ev: TripEvent) => {
      if (seen.has(ev.seq)) return;
      seen.add(ev.seq);
      setEvents((prev) => [...prev, ev].sort((a, b) => a.seq - b.seq));
    };
    const finish = () => {
      if (!finished.current) {
        finished.current = true;
        onFinished();
      }
    };

    let poll: number | undefined;
    const source = new EventSource(api.streamUrl(tripId));
    source.addEventListener("progress", (e) => add(JSON.parse((e as MessageEvent).data) as TripEvent));
    source.addEventListener("status", () => {
      source.close();
      finish();
    });
    source.onerror = () => {
      // Fall back to polling if the stream is unavailable (e.g. a proxy that buffers SSE).
      if (source.readyState === EventSource.CLOSED && !poll && !finished.current) {
        poll = window.setInterval(async () => {
          try {
            const last = Math.max(0, ...seen);
            (await api.events(tripId, last)).forEach(add);
            const trip = await api.trip(tripId);
            if (trip.status === "completed" || trip.status === "failed") {
              window.clearInterval(poll);
              finish();
            }
          } catch {
            /* keep polling */
          }
        }, 2000);
      }
    };
    return () => {
      source.close();
      if (poll) window.clearInterval(poll);
    };
  }, [tripId, onFinished]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [events.length]);

  const state = (role: string): AgentState => {
    if (events.some((e) => e.agent === role && e.kind === "agent_completed")) return "done";
    if (events.some((e) => e.agent === role && e.kind === "agent_started")) return "running";
    return "pending";
  };
  const doneCount = PLANNING_AGENTS.filter((a) => state(a.role) === "done").length;

  return (
    <div className="card progress-card">
      <div className="progress-head">
        <div>
          <h2>Your agents are planning the trip</h2>
          <p className="muted">This usually takes one to three minutes. You can leave this page and come back.</p>
        </div>
        <div className="progress-count">
          {doneCount}/{PLANNING_AGENTS.length}
        </div>
      </div>
      <div className="progress-bar">
        <div style={{ width: `${(doneCount / PLANNING_AGENTS.length) * 100}%` }} />
      </div>
      <ol className="agent-steps">
        {PLANNING_AGENTS.map((a, i) => {
          const s = state(a.role);
          const tools = events.filter((e) => e.agent === a.role && e.kind === "tool");
          return (
            <li key={a.role} className={`agent-step agent-${s}`}>
              <span className="agent-dot">{s === "done" ? "✓" : i + 1}</span>
              <div>
                <div className="agent-role">{a.role}</div>
                <div className="muted small">{a.blurb}</div>
                {s === "running" && tools.length > 0 && <div className="agent-tool small">{tools[tools.length - 1].message}</div>}
              </div>
              {s === "running" && <span className="spinner" aria-label="working" />}
            </li>
          );
        })}
      </ol>
      <details className="event-log">
        <summary>Activity log ({events.length})</summary>
        <ol ref={logRef}>
          {events.map((e) => (
            <li key={e.seq} className={`log-${e.kind}`}>
              <span className="log-time">{e.created_at.slice(11, 19)}</span>
              <span className="log-agent">{e.agent}</span>
              <span>{e.message}</span>
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}
