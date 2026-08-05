import { useState, useCallback } from "react";
import type { SavedTripSummary, Itinerary } from "../types/trip";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function useSavedTrips() {
  const [trips, setTrips] = useState<SavedTripSummary[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTrips = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/trips`);
      if (!res.ok) throw new Error("Failed to fetch trips");
      const data = await res.json();
      setTrips(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load trips");
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchTrip = useCallback(async (id: string): Promise<Itinerary | null> => {
    try {
      const res = await fetch(`${API_BASE}/trips/${id}`);
      if (!res.ok) throw new Error("Failed to load trip details");
      return await res.json();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load trip");
      return null;
    }
  }, []);

  const deleteTrip = useCallback(async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/trips/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete trip");
      setTrips((prev) => prev.filter((t) => t.id !== id));
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete trip");
      return false;
    }
  }, []);

  return { trips, isLoading, error, fetchTrips, fetchTrip, deleteTrip };
}
