import { useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, RefreshCcw } from "lucide-react";
import {
  WS_BASE,
  createRule,
  deleteRule,
  getEvent,
  listEvents,
  listRules,
  replayEvent,
  updateRule
} from "./api";
import EventDetail from "./components/EventDetail";
import EventList from "./components/EventList";
import LiveStatusPanel from "./components/LiveStatusPanel";
import RuleEditor from "./components/RuleEditor";
import type { ForwardingRule, LiveMessage, RuleInput, WebhookEvent } from "./types";

function mergeEvent(events: WebhookEvent[], next: WebhookEvent): WebhookEvent[] {
  const index = events.findIndex((event) => event.id === next.id);
  if (index === -1) {
    return [next, ...events].slice(0, 100);
  }
  const copy = [...events];
  copy[index] = next;
  return copy;
}

export default function App() {
  const [events, setEvents] = useState<WebhookEvent[]>([]);
  const [rules, setRules] = useState<ForwardingRule[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [socketState, setSocketState] = useState<"connecting" | "open" | "closed">(
    "connecting"
  );
  const [messages, setMessages] = useState<LiveMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [replayingId, setReplayingId] = useState<string | null>(null);

  const selectedEvent = useMemo(
    () => events.find((event) => event.id === selectedId) ?? events[0] ?? null,
    [events, selectedId]
  );

  useEffect(() => {
    Promise.all([listEvents(), listRules()])
      .then(([nextEvents, nextRules]) => {
        setEvents(nextEvents);
        setRules(nextRules);
        setSelectedId(nextEvents[0]?.id ?? null);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const socket = new WebSocket(`${WS_BASE}/ws/events`);
    setSocketState("connecting");

    socket.addEventListener("open", () => setSocketState("open"));
    socket.addEventListener("close", () => setSocketState("closed"));
    socket.addEventListener("error", () => setSocketState("closed"));
    socket.addEventListener("message", (event) => {
      const payload = JSON.parse(event.data);
      setMessages((current) =>
        [
          {
            id: `${payload.type}-${Date.now()}`,
            type: payload.type,
            timestamp: new Date().toISOString()
          },
          ...current
        ].slice(0, 8)
      );

      if (payload.event) {
        setEvents((current) => mergeEvent(current, payload.event));
        setSelectedId((current) => current ?? payload.event.id);
      }
      if (payload.rule) {
        setRules((current) => {
          const index = current.findIndex((rule) => rule.id === payload.rule.id);
          if (index === -1) {
            return [payload.rule, ...current];
          }
          const copy = [...current];
          copy[index] = payload.rule;
          return copy;
        });
      }
      if (payload.rule_id) {
        setRules((current) => current.filter((rule) => rule.id !== payload.rule_id));
      }
    });

    return () => socket.close();
  }, []);

  async function refreshSelected(eventId: string) {
    const next = await getEvent(eventId);
    setEvents((current) => mergeEvent(current, next));
    setSelectedId(next.id);
  }

  async function handleReplay(eventId: string, overrideUrl?: string) {
    setReplayingId(eventId);
    setError(null);
    try {
      await replayEvent(eventId, overrideUrl);
      await refreshSelected(eventId);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setReplayingId(null);
    }
  }

  async function handleCreateRule(payload: RuleInput) {
    const rule = await createRule(payload);
    setRules((current) => [rule, ...current]);
  }

  async function handleToggleRule(rule: ForwardingRule) {
    const updated = await updateRule(rule.id, { enabled: !rule.enabled });
    setRules((current) =>
      current.map((item) => (item.id === updated.id ? updated : item))
    );
  }

  async function handleDeleteRule(ruleId: string) {
    await deleteRule(ruleId);
    setRules((current) => current.filter((rule) => rule.id !== ruleId));
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Local relay workspace</p>
          <h1>Webhook Relay & Inspector</h1>
        </div>
        <div className="topbar-actions">
          <span className={`socket-pill socket-pill-${socketState}`}>
            <Activity size={16} />
            {socketState}
          </span>
          <button className="icon-button" onClick={() => window.location.reload()}>
            <RefreshCcw size={18} />
          </button>
        </div>
      </header>

      {error && (
        <div className="error-banner">
          <AlertTriangle size={18} />
          <span>{error}</span>
        </div>
      )}

      <section className="workspace-grid">
        <EventList
          events={events}
          selectedId={selectedEvent?.id ?? null}
          loading={loading}
          onSelect={setSelectedId}
        />
        <EventDetail
          event={selectedEvent}
          replaying={replayingId === selectedEvent?.id}
          onReplay={handleReplay}
        />
        <aside className="side-rail">
          <RuleEditor
            rules={rules}
            onCreate={handleCreateRule}
            onToggle={handleToggleRule}
            onDelete={handleDeleteRule}
          />
          <LiveStatusPanel socketState={socketState} messages={messages} />
        </aside>
      </section>
    </main>
  );
}

