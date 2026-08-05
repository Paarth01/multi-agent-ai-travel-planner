interface PlanningErrorProps {
  message: string;
  onRetry: () => void;
}

export function PlanningError({ message, onRetry }: PlanningErrorProps) {
  return (
    <main className="flex-grow flex items-center justify-center py-xl px-margin-mobile md:px-margin-desktop">
      <div className="w-full max-w-[480px] bg-surface-container-lowest rounded-xl card-shadow border border-error-container p-xl text-center animate-fade-scale-in">
        <div className="w-14 h-14 rounded-full bg-error-container/60 flex items-center justify-center mx-auto mb-md">
          <span className="material-symbols-outlined text-error text-[28px]">error</span>
        </div>
        <h2 className="text-headline-md text-on-surface mb-xs">We hit a snag</h2>
        <p className="text-body-md text-on-surface-variant mb-lg">{message}</p>
        <button
          onClick={onRetry}
          className="bg-primary text-on-primary px-lg py-md rounded-lg text-label-md active:scale-95 transition-transform duration-150"
        >
          Try again
        </button>
      </div>
    </main>
  );
}
