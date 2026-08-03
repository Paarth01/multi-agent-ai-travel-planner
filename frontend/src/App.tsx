import { useState } from "react";
import { Header } from "./components/Header";
import { Footer } from "./components/Footer";
import { TripRequestForm } from "./components/TripRequestForm";
import { AgentProgress } from "./components/AgentProgress";
import { ItineraryLoadingSkeleton } from "./components/ItineraryLoadingSkeleton";
import { ItineraryView } from "./components/ItineraryView";
import { PlanningError } from "./components/PlanningError";
import { useTripPlannerSSE } from "./hooks/useTripPlannerSSE";
import type { TripRequest } from "./types/trip";

function App() {
  const { phase, board, timeline, itinerary, errorMessage, planTrip, reset } = useTripPlannerSSE();
  const [destination, setDestination] = useState("");

  const handleSubmit = (request: TripRequest) => {
    setDestination(request.destination);
    planTrip(request);
  };

  // "planning" phase: show live agent progress until the itinerary_ready
  // event arrives. The loading skeleton covers the brief transition
  // window right as synthesize fires but before phase flips to
  // "complete" — kept here for the visual transition Stitch designed.
  const showLoadingSkeleton = phase === "planning" && itinerary !== null;

  return (
    <div className="bg-surface text-on-surface flex flex-col min-h-screen">
      <Header activeTab={phase === "idle" ? "new-trip" : "my-trips"} />

      {phase === "idle" && <TripRequestForm onSubmit={handleSubmit} isSubmitting={false} />}

      {phase === "planning" && !showLoadingSkeleton && (
        <AgentProgress destination={destination} board={board} timeline={timeline} />
      )}

      {showLoadingSkeleton && <ItineraryLoadingSkeleton />}

      {phase === "complete" && itinerary && <ItineraryView itinerary={itinerary} onPlanAnother={reset} />}

      {phase === "error" && (
        <PlanningError message={errorMessage ?? "Something went wrong. Please try again."} onRetry={reset} />
      )}

      <Footer
        note={
          phase === "complete" && itinerary?.best_effort
            ? `Best effort — couldn't fully fit your budget after ${itinerary.negotiation_rounds} rounds of rebalancing.`
            : undefined
        }
      />
    </div>
  );
}

export default App;
