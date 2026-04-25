export type DeliveryAttempt = {
  id: string;
  event_id: string;
  rule_id: string;
  endpoint_url: string;
  status: "queued" | "success" | "failed" | "skipped";
  attempt_number: number;
  status_code: number | null;
  error: string | null;
  duration_ms: number | null;
  created_at: string;
};

export type WebhookEvent = {
  id: string;
  source: string;
  method: string;
  path: string;
  headers: Record<string, string>;
  query_params: Record<string, string>;
  body: unknown;
  body_text: string;
  event_type: string | null;
  signature_valid: boolean | null;
  status:
    | "received"
    | "rejected"
    | "forwarded"
    | "forward_failed"
    | "replayed";
  received_at: string;
  delivery_attempts: DeliveryAttempt[];
  replay_count: number;
};

export type ForwardingRule = {
  id: string;
  name: string;
  endpoint_url: string;
  source: string | null;
  event_type: string | null;
  header_matches: Record<string, string>;
  enabled: boolean;
  max_retries: number;
  timeout_seconds: number;
  created_at: string;
};

export type RuleInput = {
  name: string;
  endpoint_url: string;
  source?: string | null;
  event_type?: string | null;
  header_matches: Record<string, string>;
  enabled: boolean;
  max_retries: number;
  timeout_seconds: number;
};

export type LiveMessage = {
  id: string;
  type: string;
  timestamp: string;
};

