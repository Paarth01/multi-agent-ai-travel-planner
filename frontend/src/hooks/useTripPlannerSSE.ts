import { useCallback, useRef, useState } from "react";
import type {
  AgentCardState,
  AgentDisplayStatus,
  Itinerary,
  NodeCompleteEvent,
  TripRequest,
} from "../types/trip";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type PlannerPhase = "idle" | "planning" | "complete" | "error";

interface AgentBoardState {
  flight_agent: AgentCardState;
  hotel_agent: AgentCardState;
  activity_agent: AgentCardState;
  pricing_agent: AgentCardState;
}

const initialBoard: AgentBoardState = {
  flight_agent: { status: "waiting", detail: "Queued." },
  hotel_agent: { status: "waiting", detail: "Queued." },
  activity_agent: { status: "waiting", detail: "Queued after accommodation." },
  pricing_agent: { status: "waiting", detail: "Waiting on agent results." },
};

export interface TimelineEntry {
  id: string;
  node: string;
  label: string;
  timestamp: number;
}

/**
 * Parses one raw SSE frame (already split on \n\n) into {event, data}.
 * Mirrors the backend's `_sse_event` formatter in api/main.py.
 */
function parseSSEBlock(block: string): { event: string; data: unknown } | null {
  let eventName: string | null = null;
  let dataLine: string | null = null;

  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) eventName = line.slice("event:".length).trim();
    else if (line.startsWith("data:")) dataLine = line.slice("data:".length).trim();
  }

  if (!eventName || dataLine === null) return null;
  try {
    return { event: eventName, data: JSON.parse(dataLine) };
  } catch {
    return null;
  }
}

function labelForNode(node: string, data: NodeCompleteEvent): string {
  switch (node) {
    case "flight_agent":
      return "Flight found";
    case "hotel_agent":
      return "Hotel found";
    case "activity_agent":
      return "Activities planned";
    case "pricing_agent":
      return data.is_over_budget ? "Over budget — rebalancing needed" : "Budget check passed";
    case "reallocate":
      return `Reallocating budget (round ${data.negotiation_round ?? "?"})`;
    case "synthesize":
      return "Itinerary assembled";
    default:
      return node;
  }
}

export function useTripPlannerSSE() {
  const [phase, setPhase] = useState<PlannerPhase>("idle");
  const [board, setBoard] = useState<AgentBoardState>(initialBoard);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [itinerary, setItinerary] = useState<Itinerary | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const updateAgentStatus = useCallback((node: string, status: AgentDisplayStatus, detail: string) => {
    setBoard((prev) => {
      if (node in prev) {
        return { ...prev, [node]: { status, detail } };
      }
      return prev;
    });
  }, []);

  const planTrip = useCallback(async (request: TripRequest, maxNegotiationRounds = 3) => {
    setPhase("planning");
    setItinerary(null);
    setErrorMessage(null);
    setTimeline([]);
    setBoard({
      flight_agent: { status: "searching", detail: "Searching for flights..." },
      hotel_agent: { status: "waiting", detail: "Queued." },
      activity_agent: { status: "waiting", detail: "Queued." },
      pricing_agent: { status: "waiting", detail: "Waiting on agent results." },
    });

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch(`${API_BASE}/plan-trip`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...request, max_negotiation_rounds: maxNegotiationRounds }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`Trip planning request failed (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? ""; // last chunk may be incomplete, keep buffering

        for (const rawBlock of blocks) {
          if (!rawBlock.trim()) continue;
          const parsed = parseSSEBlock(rawBlock);
          if (!parsed) continue;

          if (parsed.event === "node_complete") {
            const data = parsed.data as NodeCompleteEvent;
            const node = data.node;

            if (node === "flight_agent" || node === "hotel_agent" || node === "activity_agent") {
              updateAgentStatus(node, "found", labelForNode(node, data));
              // Kick off the next queued agent visually if it hasn't started
              if (node === "flight_agent") updateAgentStatus("hotel_agent", "searching", "Searching for hotels...");
              if (node === "hotel_agent") updateAgentStatus("activity_agent", "searching", "Finding activities...");
            } else if (node === "pricing_agent") {
              updateAgentStatus(
                "pricing_agent",
                data.is_over_budget ? "reallocating" : "found",
                labelForNode(node, data)
              );
            } else if (node === "reallocate") {
              updateAgentStatus("pricing_agent", "reallocating", labelForNode(node, data));
            }

            setTimeline((prev) => [
              ...prev,
              { id: `${node}-${prev.length}`, node, label: labelForNode(node, data), timestamp: Date.now() },
            ]);
          }

          if (parsed.event === "itinerary_ready") {
            setItinerary(parsed.data as Itinerary);
          }

          if (parsed.event === "error") {
            const data = parsed.data as { message: string };
            setErrorMessage(data.message);
            setPhase("error");
          }

          if (parsed.event === "done") {
            setPhase((current) => (current === "error" ? current : "complete"));
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setErrorMessage((err as Error).message ?? "Something went wrong while planning your trip.");
        setPhase("error");
      }
    }
  }, [updateAgentStatus]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setPhase("idle");
    setBoard(initialBoard);
    setTimeline([]);
    setItinerary(null);
    setErrorMessage(null);
  }, []);

  return { phase, board, timeline, itinerary, errorMessage, planTrip, reset };
}
