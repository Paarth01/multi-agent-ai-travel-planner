interface HeaderProps {
  activeTab?: "new-trip" | "my-trips";
}

export function Header({ activeTab = "new-trip" }: HeaderProps) {
  return (
    <header className="bg-surface-container-lowest w-full top-0 sticky border-b border-surface-variant shadow-sm z-50">
      <div className="flex justify-between items-center h-16 px-margin-mobile md:px-margin-desktop max-w-[1440px] mx-auto">
        <div className="flex items-center gap-sm">
          <div className="h-8 w-8 rounded-lg bg-primary-container/20 flex items-center justify-center">
            <span className="material-symbols-outlined text-primary text-[20px]">travel_explore</span>
          </div>
          <span className="font-bold text-headline-md text-primary">TripSync AI</span>
        </div>
        <nav className="hidden md:flex items-center gap-xl">
          <a
            className={
              activeTab === "new-trip"
                ? "text-primary border-b-2 border-primary font-bold pb-1 text-body-md"
                : "text-on-surface-variant hover:text-primary transition-colors text-body-md"
            }
            href="#"
          >
            New Trip
          </a>
          <a
            className={
              activeTab === "my-trips"
                ? "text-primary border-b-2 border-primary font-bold pb-1 text-body-md"
                : "text-on-surface-variant hover:text-primary transition-colors text-body-md"
            }
            href="#"
          >
            My Trips
          </a>
          <a className="text-on-surface-variant hover:text-primary transition-colors text-body-md" href="#">
            Profile
          </a>
        </nav>
        <button className="bg-primary-container text-on-primary-container px-lg py-sm rounded-lg text-label-md active:scale-95 transition-transform duration-150">
          Create Trip
        </button>
      </div>
    </header>
  );
}
