export function ItineraryLoadingSkeleton() {
  const shimmer = "bg-surface-container-high rounded-lg animate-pulse";

  return (
    <main className="flex-grow max-w-[1440px] mx-auto px-margin-mobile md:px-margin-desktop py-xl w-full">
      <div className="mb-xl space-y-sm">
        <div className={`h-8 w-64 ${shimmer}`} />
        <div className={`h-4 w-40 ${shimmer}`} />
      </div>

      <div className={`h-24 w-full ${shimmer} mb-xl`} />

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-xl">
        <div className="space-y-lg">
          <div className={`h-48 w-full ${shimmer}`} />
          <div className={`h-64 w-full ${shimmer}`} />
        </div>
        <div className="space-y-md">
          <div className={`h-6 w-56 ${shimmer}`} />
          <div className={`h-20 w-full ${shimmer}`} />
          <div className={`h-20 w-full ${shimmer}`} />
        </div>
      </div>
    </main>
  );
}
