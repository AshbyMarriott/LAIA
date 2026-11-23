/** Types mirrored from LAIA FastAPI schemas (src/laia/schemas/). */

export type PendingType = 'disambiguation' | 'confirmation' | 'slot_clarification';

export interface PendingDisambiguationOption {
  id: string;
  label: string;
}

export interface PendingState {
  type: PendingType;
  command?: string | null;
  options?: PendingDisambiguationOption[] | null;
  target_event_id?: string | null;
  clarification_question?: string | null;
}

export interface ActionResult {
  command: string;
  result: Record<string, unknown>;
}

export interface ChatRequest {
  conversation_id?: string | null;
  message: string;
}

export interface ChatResponse {
  conversation_id: string;
  reply: string;
  action: ActionResult | null;
  pending: PendingState | null;
}

export interface EventRead {
  id: string;
  title: string;
  description: string | null;
  location: string | null;
  start_at: string;
  end_at: string;
  timezone: string;
  all_day: boolean;
  created_at: string;
  updated_at: string;
}

export interface EventList {
  items: EventRead[];
  total: number;
}

export interface OllamaHealth {
  ok?: boolean;
  status?: string;
  model?: string;
  [key: string]: unknown;
}

export interface ConnectionCheckResult {
  apiOk: boolean;
  ollamaOk: boolean;
  ollama?: OllamaHealth;
  error?: string;
}
