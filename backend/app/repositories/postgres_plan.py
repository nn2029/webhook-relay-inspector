"""PostgreSQL migration notes for the repository layer.

The in-memory repositories are intentionally shaped around operations that map
cleanly to SQL tables: events, forwarding_rules, and delivery_attempts. A future
adapter can implement the same methods with transactions, row-level ownership,
indexed filters, and a retention job.
"""

EVENTS_TABLE_DDL = """
create table webhook_events (
  id text primary key,
  source text not null,
  method text not null,
  path text not null,
  headers jsonb not null,
  query_params jsonb not null,
  raw_body bytea not null,
  json_payload jsonb,
  event_type text,
  signature_valid boolean,
  status text not null,
  received_at timestamptz not null,
  replay_count integer not null default 0
);

create index webhook_events_received_at_idx on webhook_events (received_at desc);
create index webhook_events_source_type_idx on webhook_events (source, event_type);
"""

FORWARDING_RULES_TABLE_DDL = """
create table forwarding_rules (
  id text primary key,
  name text not null,
  endpoint_url text not null,
  source text,
  event_type text,
  header_matches jsonb not null default '{}',
  enabled boolean not null default true,
  max_retries integer not null default 2,
  timeout_seconds numeric not null default 5,
  created_at timestamptz not null
);
"""

DELIVERY_ATTEMPTS_TABLE_DDL = """
create table delivery_attempts (
  id text primary key,
  event_id text not null references webhook_events(id) on delete cascade,
  rule_id text not null references forwarding_rules(id),
  endpoint_url text not null,
  status text not null,
  attempt_number integer not null,
  status_code integer,
  error text,
  duration_ms numeric,
  created_at timestamptz not null
);

create index delivery_attempts_event_idx on delivery_attempts (event_id, created_at);
"""

