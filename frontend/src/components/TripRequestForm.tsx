import { useState } from "react";
import type { TripRequest } from "../types/trip";

interface InterestOption {
  id: string;
  label: string;
  icon: string;
}

const INTERESTS: InterestOption[] = [
  { id: "beaches", label: "Beaches", icon: "beach_access" },
  { id: "nightlife", label: "Nightlife", icon: "nightlife" },
  { id: "food", label: "Food", icon: "restaurant" },
  { id: "history", label: "History", icon: "history_edu" },
  { id: "nature", label: "Nature", icon: "forest" },
];

interface FormErrors {
  destination?: string;
  origin?: string;
  start_date?: string;
  end_date?: string;
  budget?: string;
}

interface TripRequestFormProps {
  onSubmit: (request: TripRequest) => void;
  isSubmitting: boolean;
}

export function TripRequestForm({ onSubmit, isSubmitting }: TripRequestFormProps) {
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [budget, setBudget] = useState("");
  const [interests, setInterests] = useState<Set<string>>(new Set());
  const [errors, setErrors] = useState<FormErrors>({});

  const toggleInterest = (id: string) => {
    setInterests((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const validate = (): FormErrors => {
    const next: FormErrors = {};
    if (!origin.trim()) next.origin = "Please enter a starting point";
    if (!destination.trim()) next.destination = "Please enter a destination";
    if (!startDate) next.start_date = "Choose a date";
    if (!endDate) next.end_date = "Choose a date";
    if (startDate && endDate && endDate <= startDate) next.end_date = "End date must be after start date";
    if (!budget || Number(budget) <= 0) next.budget = "Enter a budget greater than 0";
    return next;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const validationErrors = validate();
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) return;

    onSubmit({
      origin: origin.trim(),
      destination: destination.trim(),
      start_date: startDate,
      end_date: endDate,
      budget: Number(budget),
      interests: Array.from(interests),
    });
  };

  const inputClass = (hasError?: string) =>
    `w-full pl-10 pr-4 py-3 rounded-lg border outline-none transition-all text-body-md bg-surface-container-lowest ${
      hasError
        ? "border-secondary focus:border-secondary focus:ring-1 focus:ring-secondary"
        : "border-outline-variant focus:border-primary focus:ring-1 focus:ring-primary"
    }`;

  return (
    <main className="flex-grow flex items-center justify-center py-xl px-margin-mobile md:px-margin-desktop relative overflow-hidden">
      <div className="absolute top-[-10%] left-[-5%] w-[40rem] h-[40rem] bg-primary/5 rounded-full blur-[100px] -z-10" />
      <div className="absolute bottom-[-10%] right-[-5%] w-[35rem] h-[35rem] bg-secondary/5 rounded-full blur-[100px] -z-10" />

      <div className="w-full max-w-[640px] bg-surface-container-lowest rounded-xl card-shadow p-lg md:p-xl animate-fade-scale-in">
        <div className="border-b border-surface-variant pb-md mb-xl">
          <h1 className="text-headline-lg text-on-surface mb-xs">Where next?</h1>
          <p className="text-body-md text-on-surface-variant">
            Tell us your preferences and let our AI craft your perfect itinerary.
          </p>
        </div>

        <form className="space-y-lg" onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
            <div className="flex flex-col gap-xs">
              <label className="text-label-md text-on-surface-variant" htmlFor="origin">
                Starting Point
              </label>
              <div className="relative">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[20px]">
                  location_on
                </span>
                <input
                  id="origin"
                  className={inputClass(errors.origin)}
                  placeholder="City or Airport"
                  type="text"
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                />
              </div>
              {errors.origin && <p className="text-body-sm text-secondary">{errors.origin}</p>}
            </div>

            <div className="flex flex-col gap-xs">
              <label className="text-label-md text-on-surface-variant" htmlFor="destination">
                Destination
              </label>
              <div className="relative">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[20px]">
                  flight_land
                </span>
                <input
                  id="destination"
                  className={inputClass(errors.destination)}
                  placeholder="Where to?"
                  type="text"
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                />
              </div>
              {errors.destination && <p className="text-body-sm text-secondary">{errors.destination}</p>}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-md">
            <div className="flex flex-col gap-xs">
              <label className="text-label-md text-on-surface-variant" htmlFor="start-date">
                Start Date
              </label>
              <div className="relative">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[20px]">
                  calendar_today
                </span>
                <input
                  id="start-date"
                  className={inputClass(errors.start_date)}
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                />
              </div>
              {errors.start_date && <p className="text-body-sm text-secondary">{errors.start_date}</p>}
            </div>

            <div className="flex flex-col gap-xs">
              <label className="text-label-md text-on-surface-variant" htmlFor="end-date">
                End Date
              </label>
              <div className="relative">
                <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[20px]">
                  event
                </span>
                <input
                  id="end-date"
                  className={inputClass(errors.end_date)}
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>
              {errors.end_date && <p className="text-body-sm text-secondary">{errors.end_date}</p>}
            </div>
          </div>

          <div className="flex flex-col gap-xs">
            <label className="text-label-md text-on-surface-variant" htmlFor="budget">
              Approximate Budget
            </label>
            <div className="relative">
              <div className="absolute left-3 top-1/2 -translate-y-1/2 text-label-md text-outline">₹</div>
              <input
                id="budget"
                className={`${inputClass(errors.budget)} pl-8`}
                placeholder="Amount"
                type="number"
                min="0"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
              />
            </div>
            {errors.budget && <p className="text-body-sm text-secondary">{errors.budget}</p>}
          </div>

          <div className="flex flex-col gap-md">
            <label className="text-label-md text-on-surface-variant">What are you interested in?</label>
            <div className="flex flex-wrap gap-sm">
              {INTERESTS.map((interest) => {
                const active = interests.has(interest.id);
                return (
                  <button
                    key={interest.id}
                    type="button"
                    onClick={() => toggleInterest(interest.id)}
                    className={`px-md py-2 rounded-full border text-label-md transition-all duration-150 flex items-center gap-xs active:scale-95 ${
                      active
                        ? "chip-active"
                        : "border-outline-variant text-on-surface-variant hover:border-primary"
                    }`}
                  >
                    <span className="material-symbols-outlined text-[18px]">{interest.icon}</span>
                    {interest.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="pt-md">
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-primary text-on-primary py-lg rounded-lg text-headline-md shadow-lg shadow-primary/20 hover:bg-primary-container active:scale-[0.98] transition-all duration-150 flex items-center justify-center gap-md disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <span className="w-5 h-5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  Planning your trip...
                </>
              ) : (
                <>
                  Plan My Trip
                  <span className="material-symbols-outlined">auto_awesome</span>
                </>
              )}
            </button>
            <p className="text-center mt-md text-body-sm text-on-surface-variant opacity-70">
              Our AI analyzes 10,000+ data points to build your route.
            </p>
          </div>
        </form>
      </div>
    </main>
  );
}
