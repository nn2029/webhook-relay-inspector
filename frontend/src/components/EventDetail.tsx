import { Copy, RotateCcw, ShieldCheck, ShieldX } from "lucide-react";
import { useState } from "react";
import type { WebhookEvent } from "../types";

type Props = {
  event: WebhookEvent | null;
  replaying: boolean;
  onReplay: (eventId: string, overrideUrl?: string) => Promise<void>;
};

export default function EventDetail({ event, replaying, onReplay }: Props) {
  const [overrideUrl, setOverrideUrl] = useState("");

  if (!event) {
    return (
      <section className="panel detail-panel empty-detail">
        <p className="eyebrow">Detail</p>
        <h2>No event selected</h2>
      </section>
    );
  }

  const signatureIcon =
    event.signature_valid === false ? <ShieldX size={16} /> : <ShieldCheck size={16} />;

  return (
    <section className="panel detail-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Event detail</p>
          <h2>{event.event_type ?? event.id}</h2>
        </div>
        <span className={`signature-badge signature-${event.signature_valid}`}>
          {signatureIcon}
          {event.signature_valid === null
            ? "unsigned"
            : event.signature_valid
              ? "verified"
              : "invalid"}
        </span>
      </div>

      <div className="metadata-grid">
        <div>
          <span>Source</span>
          <strong>{event.source}</strong>
        </div>
        <div>
          <span>Status</span>
          <strong>{event.status}</strong>
        </div>
        <div>
          <span>Replay count</span>
          <strong>{event.replay_count}</strong>
        </div>
        <div>
          <span>Received</span>
          <strong>{new Date(event.received_at).toLocaleString()}</strong>
        </div>
      </div>

      <div className="replay-bar">
        <input
          value={overrideUrl}
          onChange={(event) => setOverrideUrl(event.target.value)}
          placeholder="Optional one-off replay URL"
        />
        <button
          className="primary-button"
          onClick={() => onReplay(event.id, overrideUrl)}
          disabled={replaying}
        >
          <RotateCcw size={17} />
          {replaying ? "Replaying" : "Replay"}
        </button>
      </div>

      <div className="json-toolbar">
        <h3>Payload</h3>
        <button
          className="icon-button"
          onClick={() => navigator.clipboard.writeText(JSON.stringify(event.body, null, 2))}
        >
          <Copy size={16} />
        </button>
      </div>
      <pre className="json-viewer">{JSON.stringify(event.body, null, 2)}</pre>

      <div className="attempts">
        <h3>Delivery attempts</h3>
        {event.delivery_attempts.length === 0 && (
          <p className="muted">No delivery attempts recorded.</p>
        )}
        {event.delivery_attempts.map((attempt) => (
          <div className="attempt-row" key={attempt.id}>
            <span className={`attempt-status attempt-${attempt.status}`}>
              {attempt.status}
            </span>
            <span>{attempt.endpoint_url}</span>
            <strong>{attempt.status_code ?? "no response"}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

