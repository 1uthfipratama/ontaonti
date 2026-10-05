export type Role = "admin" | "agent" | "reviewer";
export type Channel = "whatsapp" | "messenger" | "instagram";
export type Severity = "none" | "low" | "high" | "emergency";

export interface Staff {
  id: number;
  email: string;
  name: string;
  role: Role;
  is_active: boolean;
}

export interface Identity {
  id: number;
  contact_id: number;
  channel: Channel;
  external_id: string;
  display_name: string;
  simulated: boolean;
  last_seen_at: string | null;
}

export interface Contact {
  id: number;
  display_name: string;
  phone: string | null;
  notes: string;
  opted_out: boolean;
  broadcast_opt_in: boolean;
  created_at: string;
  identities: Identity[];
}

export interface Conversation {
  id: number;
  contact_id: number;
  contact_name: string;
  identity: Identity | null;
  channel: Channel;
  simulated: boolean;
  status: "OPEN" | "RESOLVED";
  mode: "BOT" | "HUMAN";
  assigned_to: number | null;
  window_expires_at: string | null;
  last_message_at: string | null;
  last_inbound_at: string | null;
  last_preview: string;
  unread_count: number;
  flag_severity: Severity;
  flag_category: string | null;
  opted_out: boolean;
  labels: LabelRef[];
  contact?: Contact;
}

export interface LabelRef {
  id: number;
  name: string;
}

export interface SavedReply {
  id: number;
  shortcut: string;
  title: string;
  body: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  direction: "in" | "out" | "note";
  sender_type: "user" | "bot" | "agent" | "system";
  sender_staff_id: number | null;
  text: string;
  kind: string;
  media_url: string | null;
  status: string;
  error: string | null;
  flag_severity: Severity | null;
  flag_category: string | null;
  flag_reason: string | null;
  tokens_in: number;
  tokens_out: number;
  cost_idr: number;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface Case {
  id: number;
  conversation_id: number;
  contact_id: number;
  contact_name: string;
  channel: Channel;
  severity: Severity;
  category: string;
  reason: string;
  status: "OPEN" | "CLAIMED" | "RESOLVED";
  assigned_to: number | null;
  assigned_name: string | null;
  trigger_text: string | null;
  created_at: string;
  claimed_at: string | null;
  resolved_at: string | null;
  conversation_mode?: string;
  notes?: { id: number; author: string; text: string; created_at: string }[];
}

export interface AuditRow {
  id: number;
  created_at: string;
  actor_email: string;
  action: string;
  entity_type: string;
  entity_id: string;
  details: Record<string, unknown>;
  ip: string;
}
