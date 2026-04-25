import { PlugZap, Power, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";
import type { ForwardingRule, RuleInput } from "../types";

type Props = {
  rules: ForwardingRule[];
  onCreate: (payload: RuleInput) => Promise<void>;
  onToggle: (rule: ForwardingRule) => Promise<void>;
  onDelete: (ruleId: string) => Promise<void>;
};

const blankRule = {
  name: "",
  endpoint_url: "",
  source: "",
  event_type: "",
  header_matches: "{}",
  enabled: true,
  max_retries: 2,
  timeout_seconds: 5
};

export default function RuleEditor({ rules, onCreate, onToggle, onDelete }: Props) {
  const [form, setForm] = useState(blankRule);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const headerMatches = JSON.parse(form.header_matches || "{}");
      await onCreate({
        name: form.name,
        endpoint_url: form.endpoint_url,
        source: form.source || null,
        event_type: form.event_type || null,
        header_matches: headerMatches,
        enabled: form.enabled,
        max_retries: form.max_retries,
        timeout_seconds: form.timeout_seconds
      });
      setForm(blankRule);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel rules-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Relay</p>
          <h2>Forwarding rules</h2>
        </div>
        <span className="counter">{rules.length}</span>
      </div>

      <form className="rule-form" onSubmit={submit}>
        <input
          required
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
          placeholder="Rule name"
        />
        <input
          required
          value={form.endpoint_url}
          onChange={(event) => setForm({ ...form, endpoint_url: event.target.value })}
          placeholder="https://receiver.example/webhook"
          type="url"
        />
        <div className="two-column">
          <input
            value={form.source}
            onChange={(event) => setForm({ ...form, source: event.target.value })}
            placeholder="source"
          />
          <input
            value={form.event_type}
            onChange={(event) => setForm({ ...form, event_type: event.target.value })}
            placeholder="event type"
          />
        </div>
        <textarea
          value={form.header_matches}
          onChange={(event) => setForm({ ...form, header_matches: event.target.value })}
          rows={3}
        />
        <div className="two-column">
          <label>
            Retries
            <input
              min={0}
              max={8}
              type="number"
              value={form.max_retries}
              onChange={(event) =>
                setForm({ ...form, max_retries: Number(event.target.value) })
              }
            />
          </label>
          <label>
            Timeout
            <input
              min={1}
              max={30}
              type="number"
              value={form.timeout_seconds}
              onChange={(event) =>
                setForm({ ...form, timeout_seconds: Number(event.target.value) })
              }
            />
          </label>
        </div>
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" disabled={saving}>
          <PlugZap size={17} />
          {saving ? "Saving" : "Add rule"}
        </button>
      </form>

      <div className="rules-list">
        {rules.map((rule) => (
          <article key={rule.id} className="rule-row">
            <div>
              <strong>{rule.name}</strong>
              <span>{rule.endpoint_url}</span>
            </div>
            <div className="rule-actions">
              <button className="icon-button" onClick={() => onToggle(rule)}>
                <Power size={16} />
              </button>
              <button className="icon-button danger" onClick={() => onDelete(rule.id)}>
                <Trash2 size={16} />
              </button>
            </div>
            <span className={`rule-state ${rule.enabled ? "enabled" : "disabled"}`}>
              {rule.enabled ? "enabled" : "disabled"}
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}

