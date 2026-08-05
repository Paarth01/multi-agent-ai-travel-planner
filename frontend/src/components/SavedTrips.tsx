import { useEffect } from "react";
import { useSavedTrips } from "../hooks/useSavedTrips";

interface SavedTripsProps {
  onViewTrip: (id: string) => void;
  onCreateNew: () => void;
}

function formatCurrency(amount: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(amount);
}

export function SavedTrips({ onViewTrip, onCreateNew }: SavedTripsProps) {
  const { trips, isLoading, error, fetchTrips, deleteTrip } = useSavedTrips();

  useEffect(() => {
    fetchTrips();
  }, [fetchTrips]);

  if (isLoading) {
    return (
      <main className="flex-grow max-w-[1440px] mx-auto px-margin-mobile md:px-margin-desktop py-xl w-full">
        <div className="h-8 w-48 bg-surface-container-high rounded-lg animate-pulse mb-xl" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-lg">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-48 bg-surface-container-high rounded-xl animate-pulse" />
          ))}
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex-grow max-w-[1440px] mx-auto px-margin-mobile md:px-margin-desktop py-xl w-full">
        <div className="bg-error-container/20 border border-error-container text-on-surface p-lg rounded-xl flex items-center justify-between">
          <span>Failed to load saved trips: {error}</span>
          <button onClick={() => fetchTrips()} className="text-primary hover:underline">Retry</button>
        </div>
      </main>
    );
  }

  return (
    <main className="flex-grow max-w-[1440px] mx-auto px-margin-mobile md:px-margin-desktop py-xl w-full animate-fade-scale-in">
      <div className="flex justify-between items-center mb-xl">
        <h1 className="text-headline-lg text-on-surface">My Trips</h1>
        {trips.length > 0 && (
          <button 
            onClick={onCreateNew}
            className="flex items-center gap-xs text-primary text-label-md hover:underline"
          >
            <span className="material-symbols-outlined text-[18px]">add</span>
            New Trip
          </button>
        )}
      </div>

      {trips.length === 0 ? (
        <div className="text-center py-24 bg-surface-container-lowest rounded-xl card-shadow border border-surface-variant">
          <span className="material-symbols-outlined text-[48px] text-outline mb-md">travel_explore</span>
          <h2 className="text-headline-md text-on-surface mb-xs">No trips yet</h2>
          <p className="text-body-md text-on-surface-variant mb-lg">Start planning your first adventure.</p>
          <button
            onClick={onCreateNew}
            className="bg-primary text-on-primary px-lg py-md rounded-lg text-label-md hover:bg-primary-container active:scale-[0.98] transition-all"
          >
            Plan a Trip
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-lg">
          {trips.map(trip => (
            <div key={trip.id} className="bg-surface-container-lowest rounded-xl card-shadow border border-surface-variant overflow-hidden hover:border-primary/30 transition-colors flex flex-col">
              <div className="p-lg flex-grow cursor-pointer" onClick={() => onViewTrip(trip.id)}>
                <div className="flex justify-between items-start mb-md">
                  <h2 className="text-headline-sm text-on-surface">{trip.destination}</h2>
                  {trip.best_effort && (
                    <span className="bg-tertiary-container/20 text-tertiary px-xs py-[2px] rounded text-[10px] uppercase font-bold tracking-wide">
                      Best Effort
                    </span>
                  )}
                </div>
                <p className="text-body-sm text-on-surface-variant flex items-center gap-xs mb-sm">
                  <span className="material-symbols-outlined text-[16px]">flight_takeoff</span>
                  From {trip.origin}
                </p>
                <p className="text-body-sm text-on-surface-variant flex items-center gap-xs mb-sm">
                  <span className="material-symbols-outlined text-[16px]">calendar_today</span>
                  {trip.start_date} to {trip.end_date}
                </p>
                <p className="text-label-md text-on-surface mt-md pt-md border-t border-surface-variant">
                  {formatCurrency(trip.total_cost)}
                </p>
              </div>
              <div className="bg-surface-container-low px-lg py-sm flex justify-between items-center border-t border-surface-variant">
                <span className="text-[12px] text-on-surface-variant">
                  Created {new Date(trip.created_at).toLocaleDateString()}
                </span>
                <button 
                  onClick={(e) => {
                    e.stopPropagation();
                    if(confirm("Delete this trip?")) deleteTrip(trip.id);
                  }}
                  className="text-on-surface-variant hover:text-secondary transition-colors"
                  title="Delete Trip"
                >
                  <span className="material-symbols-outlined text-[18px]">delete</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
