import type { ForwardingRule, RuleInput, WebhookEvent } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const WS_BASE =
  import.meta.env.VITE_WS_BASE_URL ?? API_BASE.replace(/^http/, "ws");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with HTTP ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function listEvents(): Promise<WebhookEvent[]> {
  const data = await request<{ events: WebhookEvent[] }>("/events?limit=100");
  return data.events;
}

export async function getEvent(eventId: string): Promise<WebhookEvent> {
  return request<WebhookEvent>(`/events/${eventId}`);
}

export async function replayEvent(
  eventId: string,
  overrideUrl?: string
): Promise<void> {
  await request(`/events/${eventId}/replay`, {
    method: "POST",
    body: JSON.stringify({
      override_url: overrideUrl?.trim() || null
    })
  });
}

export async function listRules(): Promise<ForwardingRule[]> {
  const data = await request<{ rules: ForwardingRule[] }>("/rules");
  return data.rules;
}

export async function createRule(payload: RuleInput): Promise<ForwardingRule> {
  return request<ForwardingRule>("/rules", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function updateRule(
  ruleId: string,
  payload: Partial<RuleInput>
): Promise<ForwardingRule> {
  return request<ForwardingRule>(`/rules/${ruleId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export async function deleteRule(ruleId: string): Promise<void> {
  await request(`/rules/${ruleId}`, { method: "DELETE" });
}

