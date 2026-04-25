import { CheckCircle2, Clock3, RotateCcw, XCircle } from "lucide-react";
import type { WebhookEvent } from "../types";

type Props = {
  events: WebhookEvent[];
  selectedId: string | null;
  loading: boolean;
  onSelect: (eventId: string) => void;
};

const statusIcon = {
  received: Clock3,
  rejected: XCircle,
  forwarded: CheckCircle2,
  forward_failed: XCircle,
  replayed: RotateCcw
};

export default function EventList({ events, selectedId, loading, onSelect }: Props) {
  return (
    <section className="panel event-list-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Inbound</p>
          <h2>Events</h2>
        </div>
        <span className="counter">{events.length}</span>
      </div>

      <div className="event-list">
        {loading && <div className="empty-state">Loading events...</div>}
        {!loading && events.length === 0 && (
          <div className="empty-state">Waiting for the first webhook.</div>
        )}
        {events.map((event) => {
          const Icon = statusIcon[event.status];
          return (
            <button
              key={event.id}
              className={`event-row ${selectedId === event.id ? "selected" : ""}`}
              onClick={() => onSelect(event.id)}
            >
              <span className={`status-dot status-${event.status}`}>
                <Icon size={16} />
              </span>
              <span className="event-row-main">
                <strong>{event.event_type ?? "unknown event"}</strong>
                <span>{event.source}</span>
              </span>
              <time>{new Date(event.received_at).toLocaleTimeString()}</time>
            </button>
          );
        })}
      </div>
    </section>
  );
}

