import { Radio } from "lucide-react";
import type { LiveMessage } from "../types";

type Props = {
  socketState: "connecting" | "open" | "closed";
  messages: LiveMessage[];
};

export default function LiveStatusPanel({ socketState, messages }: Props) {
  return (
    <section className="panel live-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">WebSocket</p>
          <h2>Live status</h2>
        </div>
        <span className={`socket-light ${socketState}`} />
      </div>
      <div className="live-state">
        <Radio size={18} />
        <strong>{socketState}</strong>
      </div>
      <div className="message-list">
        {messages.length === 0 && <p className="muted">No live messages yet.</p>}
        {messages.map((message) => (
          <div className="message-row" key={message.id}>
            <span>{message.type}</span>
            <time>{new Date(message.timestamp).toLocaleTimeString()}</time>
          </div>
        ))}
      </div>
    </section>
  );
}

