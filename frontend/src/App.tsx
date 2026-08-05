import { useState } from "react";
import { Header } from "./components/Header";
import { Footer } from "./components/Footer";
import { TripRequestForm } from "./components/TripRequestForm";
import { AgentProgress } from "./components/AgentProgress";
import { ItineraryLoadingSkeleton } from "./components/ItineraryLoadingSkeleton";
import { ItineraryView } from "./components/ItineraryView";
import { PlanningError } from "./components/PlanningError";
import { SavedTrips } from "./components/SavedTrips";
import { useTripPlannerSSE } from "./hooks/useTripPlannerSSE";
import { useSavedTrips } from "./hooks/useSavedTrips";
import type { TripRequest, Itinerary } from "./types/trip";

function App() {
  const { phase, board, timeline, itinerary: plannedItinerary, errorMessage, planTrip, reset } = useTripPlannerSSE();
  const { fetchTrip } = useSavedTrips();
  const [destination, setDestination] = useState("");
  const [activeTab, setActiveTab] = useState<"new-trip" | "my-trips">("new-trip");
  const [viewedItinerary, setViewedItinerary] = useState<Itinerary | null>(null);

  const handleSubmit = (request: TripRequest) => {
    setDestination(request.destination);
    setViewedItinerary(null);
    setActiveTab("new-trip");
    planTrip(request);
  };

  const handleTabChange = (tab: "new-trip" | "my-trips") => {
    setActiveTab(tab);
    if (tab === "new-trip") {
      reset();
      setViewedItinerary(null);
    }
  };

  const handleViewTrip = async (id: string) => {
    const trip = await fetchTrip(id);
    if (trip) {
      reset();
      setViewedItinerary(trip);
      setActiveTab("new-trip");
    }
  };

  const showLoadingSkeleton = phase === "planning" && plannedItinerary !== null;
  const activeItinerary = viewedItinerary || plannedItinerary;

  return (
    <div className="bg-surface text-on-surface flex flex-col min-h-screen">
      <Header activeTab={activeTab} onTabChange={handleTabChange} />

      {activeTab === "my-trips" ? (
        <SavedTrips onViewTrip={handleViewTrip} onCreateNew={() => handleTabChange("new-trip")} />
      ) : (
        <>
          {phase === "idle" && !viewedItinerary && <TripRequestForm onSubmit={handleSubmit} isSubmitting={false} />}

          {phase === "planning" && !showLoadingSkeleton && (
            <AgentProgress destination={destination} board={board} timeline={timeline} />
          )}

          {showLoadingSkeleton && <ItineraryLoadingSkeleton />}

          {(phase === "complete" || viewedItinerary) && activeItinerary && (
            <ItineraryView itinerary={activeItinerary} onPlanAnother={() => handleTabChange("new-trip")} />
          )}

          {phase === "error" && (
            <PlanningError message={errorMessage ?? "Something went wrong. Please try again."} onRetry={reset} />
          )}
        </>
      )}

      <Footer
        note={
          activeItinerary?.best_effort
            ? `Best effort — couldn't fully fit your budget after ${activeItinerary.negotiation_rounds} rounds of rebalancing.`
            : undefined
        }
      />
    </div>
  );
}

export default App;
