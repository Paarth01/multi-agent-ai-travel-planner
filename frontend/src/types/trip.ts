// Mirrors schemas/messages.py — keep these in sync with the backend.

export type AgentNodeName =
  | "flight_agent"
  | "hotel_agent"
  | "activity_agent"
  | "pricing_agent"
  | "reallocate"
  | "synthesize";

export type BudgetCategory = "flight" | "hotel" | "activity";

export interface TripRequest {
  destination: string;
  origin: string;
  start_date: string; // ISO date, e.g. "2026-12-20"
  end_date: string;
  budget: number;
  interests: string[];
  currency?: string;
}

export interface FlightOption {
  airline: string;
  flight_number: string;
  departure_time: string;
  arrival_time: string;
  price: number;
  stops: number;
}

export interface HotelOption {
  name: string;
  area: string;
  price_per_night: number;
  total_price: number;
  rating?: number;
  amenities: string[];
}

export interface ActivitySuggestion {
  name: string;
  category: string;
  day: number;
  estimated_cost: number;
  duration_hours: number;
}

export interface BudgetLine {
  category: BudgetCategory;
  allocated: number;
  actual: number;
}

export interface Itinerary {
  trip_request: TripRequest;
  flight: FlightOption | null;
  hotel: HotelOption | null;
  activities: ActivitySuggestion[];
  budget_breakdown: BudgetLine[];
  total_cost: number;
  negotiation_rounds: number;
  best_effort: boolean;
  generated_at: string;
}

// ---- SSE event payloads from POST /plan-trip ----

export interface NodeCompleteEvent {
  node: AgentNodeName;
  status: string | null;
  is_over_budget: boolean | null;
  negotiation_round: number | null;
}

export type SSEEventType = "node_complete" | "itinerary_ready" | "done" | "error";

export interface SSEEvent {
  event: SSEEventType;
  data: NodeCompleteEvent | Itinerary | { message: string } | Record<string, never>;
}

// ---- UI-only derived state ----

export type AgentDisplayStatus = "waiting" | "searching" | "found" | "reallocating" | "failed";

export interface AgentCardState {
  status: AgentDisplayStatus;
  detail: string;
}
