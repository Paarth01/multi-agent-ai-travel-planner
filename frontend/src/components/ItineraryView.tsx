import { Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip, type ChartOptions } from "chart.js";
import { Bar } from "react-chartjs-2";
import type { Itinerary } from "../types/trip";

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip);

interface ItineraryViewProps {
  itinerary: Itinerary;
  onPlanAnother: () => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  flight: "#00685f", // primary
  hotel: "#b90538", // secondary
  activity: "#cea700", // tertiary
};

const CATEGORY_LABELS: Record<string, string> = {
  flight: "Flight",
  hotel: "Hotel",
  activity: "Activities",
};

function formatCurrency(amount: number, currency: string) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
}

export function ItineraryView({ itinerary, onPlanAnother }: ItineraryViewProps) {
  const { trip_request, flight, hotel, activities, budget_breakdown, total_cost, negotiation_rounds, best_effort } =
    itinerary;
  const currency = trip_request.currency ?? "INR";

  const chartData = {
    labels: ["Budget"],
    datasets: budget_breakdown.map((line) => ({
      label: CATEGORY_LABELS[line.category] ?? line.category,
      data: [line.actual],
      backgroundColor: CATEGORY_COLORS[line.category] ?? "#999",
      borderRadius: 4,
    })),
  };

  const chartOptions: ChartOptions<"bar"> = {
    indexAxis: "y",
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: { stacked: true, display: false },
      y: { stacked: true, display: false },
    },
    plugins: {
      tooltip: {
        callbacks: {
          label: (ctx) => `${ctx.dataset.label}: ${formatCurrency(ctx.parsed.x ?? 0, currency)}`,
        },
      },
    },
    animation: { duration: 700, easing: "easeOutQuart" },
  };

  const activitiesByDay = activities.reduce<Record<number, typeof activities>>((acc, activity) => {
    (acc[activity.day] ??= []).push(activity);
    return acc;
  }, {});

  return (
    <main className="flex-grow max-w-[1440px] mx-auto px-margin-mobile md:px-margin-desktop py-xl w-full">
      <div className="flex flex-col md:flex-row md:justify-between md:items-start gap-md mb-xl">
        <div>
          <p className="text-body-sm text-on-surface-variant mb-xs">My Trips &gt; Current Plan</p>
          <h1 className="text-headline-lg text-on-surface">{trip_request.destination}</h1>
          <p className="text-body-md text-on-surface-variant mt-xs flex items-center gap-xs">
            <span className="material-symbols-outlined text-[18px]">calendar_today</span>
            {trip_request.start_date} — {trip_request.end_date}
          </p>
        </div>

        <div className="bg-white rounded-xl card-shadow border border-surface-variant p-lg min-w-[260px] animate-fade-scale-in">
          <div className="flex items-center justify-between mb-xs">
            <span className="text-label-sm text-on-surface-variant uppercase tracking-wide">Total Est. Cost</span>
            {best_effort ? (
              <span className="bg-tertiary-container/20 text-tertiary px-sm py-xs rounded-full text-label-sm flex items-center gap-xs">
                <span className="material-symbols-outlined text-[14px]">info</span>
                Best effort
              </span>
            ) : (
              <span className="bg-green-100 text-green-700 px-sm py-xs rounded-full text-label-sm flex items-center gap-xs">
                <span className="material-symbols-outlined text-[14px]">check_circle</span>
                Within budget
              </span>
            )}
          </div>
          <p className={`text-headline-lg ${best_effort ? "text-secondary" : "text-on-surface"}`}>
            {formatCurrency(total_cost, currency)}
            <span className="text-body-sm text-on-surface-variant font-normal">
              {" "}
              / {formatCurrency(trip_request.budget, currency)} budget
            </span>
          </p>
        </div>
      </div>

      {/* Budget breakdown */}
      <section className="bg-white rounded-xl card-shadow border border-surface-variant p-lg mb-xl">
        <div className="flex items-center justify-between mb-md">
          <h2 className="text-label-md text-on-surface uppercase tracking-wide">Budget Allocation</h2>
          <div className="flex gap-md">
            {budget_breakdown.map((line) => (
              <span key={line.category} className="flex items-center gap-xs text-body-sm text-on-surface-variant">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: CATEGORY_COLORS[line.category] }}
                />
                {CATEGORY_LABELS[line.category]}
              </span>
            ))}
          </div>
        </div>
        <div className="h-6">
          <Bar data={chartData} options={chartOptions} />
        </div>
        <div className="flex justify-between mt-sm text-body-sm text-on-surface-variant">
          {budget_breakdown.map((line) => (
            <span key={line.category}>{formatCurrency(line.actual, currency)}</span>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-xl">
        {/* Flight + Hotel */}
        <div className="space-y-lg">
          {flight && (
            <div className="bg-white rounded-xl card-shadow border border-surface-variant overflow-hidden">
              <div className="bg-surface-container-low px-lg py-md flex items-center justify-between">
                <span className="text-label-md text-primary uppercase tracking-wide">Flight Details</span>
                <span className="material-symbols-outlined text-primary">flight</span>
              </div>
              <div className="p-lg">
                <p className="text-label-md text-on-surface">{flight.airline}</p>
                <p className="text-body-sm text-on-surface-variant mb-md">{flight.flight_number}</p>
                <div className="flex items-center justify-between text-headline-sm text-on-surface">
                  <span>
                    {new Date(flight.departure_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                  <span className="text-body-sm text-on-surface-variant">
                    {flight.stops === 0 ? "Non-stop" : `${flight.stops} stop(s)`}
                  </span>
                  <span>
                    {new Date(flight.arrival_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
                <div className="border-t border-surface-variant mt-md pt-md flex justify-between">
                  <span className="text-body-md text-on-surface-variant">Price</span>
                  <span className="text-label-md text-on-surface">{formatCurrency(flight.price, currency)}</span>
                </div>
              </div>
            </div>
          )}

          {hotel && (
            <div className="bg-white rounded-xl card-shadow border border-surface-variant overflow-hidden">
              <div className="p-lg">
                <div className="flex items-center justify-between mb-xs">
                  <h3 className="text-label-md text-on-surface">{hotel.name}</h3>
                  {hotel.rating && (
                    <span className="flex items-center gap-xs text-tertiary text-body-sm">
                      <span className="material-symbols-outlined text-[16px]">star</span>
                      {hotel.rating}
                    </span>
                  )}
                </div>
                <p className="text-body-sm text-on-surface-variant mb-md">{hotel.area}</p>
                <div className="flex flex-wrap gap-xs mb-md">
                  {hotel.amenities.map((a) => (
                    <span key={a} className="text-body-sm text-on-surface-variant flex items-center gap-xs">
                      <span className="material-symbols-outlined text-[16px] text-primary">check</span>
                      {a}
                    </span>
                  ))}
                </div>
                <div className="border-t border-surface-variant pt-md flex justify-between">
                  <span className="text-body-md text-on-surface-variant">Total</span>
                  <span className="text-label-md text-on-surface">{formatCurrency(hotel.total_price, currency)}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Daily itinerary */}
        <section className="bg-white rounded-xl card-shadow border border-surface-variant p-lg">
          <h2 className="text-headline-md text-on-surface mb-lg">Daily Itinerary &amp; Activities</h2>
          <div className="space-y-xl">
            {Object.entries(activitiesByDay)
              .sort(([a], [b]) => Number(a) - Number(b))
              .map(([day, dayActivities]) => (
                <div key={day}>
                  <h3 className="text-label-md text-on-surface mb-md flex items-center gap-sm">
                    <span className="w-6 h-6 rounded-full bg-primary text-on-primary flex items-center justify-center text-label-sm">
                      {day}
                    </span>
                    Day {day}
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-md pl-8">
                    {dayActivities.map((activity, idx) => (
                      <div
                        key={idx}
                        className="bg-surface-container-low rounded-lg p-md flex justify-between items-start"
                      >
                        <div>
                          <p className="text-label-md text-on-surface">{activity.name}</p>
                          <p className="text-body-sm text-on-surface-variant">
                            {activity.duration_hours}h · {activity.category}
                          </p>
                        </div>
                        <span className="text-body-sm text-on-surface">
                          {formatCurrency(activity.estimated_cost, currency)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
          </div>
        </section>
      </div>

      <div className="mt-xl flex flex-col items-center gap-xs">
        {negotiation_rounds > 0 && (
          <p className="text-body-sm text-on-surface-variant">
            Budget rebalanced {negotiation_rounds} time{negotiation_rounds > 1 ? "s" : ""} to fit your trip.
          </p>
        )}
        <button onClick={onPlanAnother} className="text-primary text-label-md hover:underline flex items-center gap-xs">
          <span className="material-symbols-outlined text-[18px]">add</span>
          Plan another trip
        </button>
      </div>
    </main>
  );
}
