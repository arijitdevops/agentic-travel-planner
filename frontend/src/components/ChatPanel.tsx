import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import { api } from "../api/client";
import type { ChatMessage, Trip } from "../types";

const SUGGESTIONS = [
  "Make day 2 more relaxed",
  "Find a cheaper hotel",
  "Add a cooking class",
  "What should I pack?",
];

interface Props {
  trip: Trip;
  onTripUpdated: (trip: Trip) => void;
}

export default function ChatPanel({ trip, onTripUpdated }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.messages(trip.id).then(setMessages).catch(() => undefined);
  }, [trip.id]);

  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }), [messages.length, sending]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || sending) return;
    setSending(true);
    setError(null);
    setDraft("");
    const optimistic: ChatMessage = { id: -Date.now(), role: "user", content: message, changes: [], created_at: new Date().toISOString() };
    setMessages((m) => [...m, optimistic]);
    try {
      const res = await api.sendMessage(trip.id, message);
      setMessages((m) => [...m.filter((x) => x.id !== optimistic.id), res.user_message, res.assistant_message]);
      if (res.trip.plan_version !== trip.plan_version) onTripUpdated(res.trip);
    } catch (e) {
      setMessages((m) => m.filter((x) => x.id !== optimistic.id));
      setDraft(message);
      setError((e as Error).message);
    } finally {
      setSending(false);
    }
  }

  return (
    <aside className="chat card">
      <div className="chat-head">
        <h3>Trip concierge</h3>
        <p className="muted small">Ask questions or request changes - the plan updates in place.</p>
      </div>
      <div className="chat-body">
        {messages.length === 0 && (
          <div className="suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="chip" onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`bubble bubble-${m.role}`}>
            {m.role === "assistant" ? <Markdown>{m.content}</Markdown> : m.content}
            {m.changes.length > 0 && (
              <ul className="changes small">
                {m.changes.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
        {sending && (
          <div className="bubble bubble-assistant typing">
            <span />
            <span />
            <span />
          </div>
        )}
        <div ref={bottom} />
      </div>
      {error && <div className="alert alert-error small">{error}</div>}
      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault();
          void send(draft);
        }}
      >
        <input placeholder="e.g. Swap the museum on day 3 for a food tour" value={draft} onChange={(e) => setDraft(e.target.value)} disabled={sending} />
        <button className="btn btn-primary" disabled={sending || !draft.trim()}>Send</button>
      </form>
    </aside>
  );
}
