import type { AgentCardState, AgentDisplayStatus } from "../types/trip";
import type { TimelineEntry } from "../hooks/useTripPlannerSSE";

interface AgentProgressProps {
  destination: string;
  board: {
    flight_agent: AgentCardState;
    hotel_agent: AgentCardState;
    activity_agent: AgentCardState;
    pricing_agent: AgentCardState;
  };
  timeline: TimelineEntry[];
}

const AGENT_META = {
  flight_agent: { label: "Flight Agent", icon: "flight" },
  hotel_agent: { label: "Hotel Agent", icon: "bed" },
  activity_agent: { label: "Activity Agent", icon: "map" },
  pricing_agent: { label: "Pricing Agent", icon: "account_balance_wallet" },
} as const;

function StatusBadge({ status }: { status: AgentDisplayStatus }) {
  switch (status) {
    case "found":
      return (
        <span className="bg-green-100 text-green-700 px-sm py-xs rounded-full text-label-sm flex items-center gap-xs animate-fade-scale-in">
          Found <span className="material-symbols-outlined text-[14px]">check</span>
        </span>
      );
    case "searching":
      return (
        <span className="text-primary text-label-sm flex items-center gap-sm">
          <span className="w-2 h-2 rounded-full bg-primary pulse-teal" />
          Searching...
        </span>
      );
    case "reallocating":
      return (
        <span className="text-tertiary text-label-sm flex items-center gap-sm">
          <span className="w-2 h-2 rounded-full bg-tertiary animate-pulse" />
          Reallocating...
        </span>
      );
    case "failed":
      return (
        <span className="bg-error-container text-on-error-container px-sm py-xs rounded-full text-label-sm flex items-center gap-xs">
          Limited Results <span className="material-symbols-outlined text-[14px]">warning</span>
        </span>
      );
    default:
      return <span className="text-on-surface-variant text-label-sm">Waiting</span>;
  }
}

function AgentCard({
  agentKey,
  state,
}: {
  agentKey: keyof typeof AGENT_META;
  state: AgentCardState;
}) {
  const meta = AGENT_META[agentKey];
  const isActive = state.status === "found" || state.status === "reallocating";

  return (
    <div
      className={`bg-surface-container-lowest p-lg rounded-xl card-shadow border flex flex-col gap-md transition-colors duration-300 ${
        isActive ? "border-primary/30" : "border-surface-variant"
      }`}
    >
      <div className="flex justify-between items-start">
        <div
          className={`p-sm rounded-lg transition-colors duration-300 ${
            state.status === "found"
              ? "bg-primary-container/10"
              : state.status === "reallocating"
              ? "bg-tertiary-container/10"
              : state.status === "failed"
              ? "bg-error-container/40"
              : "bg-surface-container-high"
          }`}
        >
          <span
            className={`material-symbols-outlined ${
              state.status === "found"
                ? "text-primary"
                : state.status === "reallocating"
                ? "text-tertiary"
                : state.status === "failed"
                ? "text-error"
                : "text-on-surface-variant"
            }`}
          >
            {meta.icon}
          </span>
        </div>
        <StatusBadge status={state.status} />
      </div>
      <div>
        <h3 className="text-label-md text-on-surface">{meta.label}</h3>
        <p className="text-body-sm text-on-surface-variant mt-xs">{state.detail}</p>
      </div>
    </div>
  );
}

export function AgentProgress({ destination, board, timeline }: AgentProgressProps) {
  return (
    <main className="flex-grow max-w-[1440px] mx-auto px-margin-mobile md:px-margin-desktop py-xl w-full">
      <section className="mb-xl">
        <h1 className="text-headline-lg text-on-surface mb-xs">
          Planning your trip to <span className="text-primary">{destination || "your destination"}</span>...
        </h1>
        <p className="text-on-surface-variant text-body-lg">Our AI agents are coordinating your perfect itinerary.</p>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-lg mb-xl">
        <AgentCard agentKey="flight_agent" state={board.flight_agent} />
        <AgentCard agentKey="hotel_agent" state={board.hotel_agent} />
        <AgentCard agentKey="activity_agent" state={board.activity_agent} />
        <AgentCard agentKey="pricing_agent" state={board.pricing_agent} />
      </section>

      <div className="grid grid-cols-1 gap-xl">
        <section className="bg-surface-container-lowest rounded-xl card-shadow border border-surface-variant p-lg">
          <div className="flex items-center justify-between mb-lg">
            <h2 className="text-headline-md text-on-surface">Activity Stream</h2>
            <span className="px-sm py-xs bg-surface-container-low rounded-lg text-on-surface-variant text-label-sm">
              Real-time
            </span>
          </div>

          <div className="relative space-y-lg scroll-mask overflow-hidden max-h-[500px]">
            <div className="absolute left-[11px] top-4 bottom-0 w-[2px] bg-surface-variant" />

            {timeline.length === 0 && (
              <p className="text-body-sm text-on-surface-variant pl-8">Waiting for the first agent to report in...</p>
            )}

            {timeline
              .slice()
              .reverse()
              .map((entry, idx) => (
                <div
                  key={entry.id}
                  className="relative flex gap-lg pl-8 animate-fade-scale-in"
                  style={{ animationDelay: `${idx * 40}ms` }}
                >
                  <div
                    className={`absolute left-0 top-[6px] w-6 h-6 rounded-full border-4 border-surface-container-lowest z-10 ${
                      idx === 0 ? "bg-primary pulse-teal" : "bg-primary-container"
                    }`}
                  />
                  <div className="flex-grow">
                    <div className="flex justify-between items-start">
                      <span className={`text-label-md ${idx === 0 ? "text-primary" : "text-on-surface"}`}>
                        {entry.label}
                      </span>
                      <span className="text-on-surface-variant text-label-sm">
                        {idx === 0 ? "Live" : new Date(entry.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
          </div>
        </section>
      </div>
    </main>
  );
}
