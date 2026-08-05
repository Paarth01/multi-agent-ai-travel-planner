import { useDarkMode } from "../hooks/useDarkMode";

interface HeaderProps {
  activeTab?: "new-trip" | "my-trips";
  onTabChange?: (tab: "new-trip" | "my-trips") => void;
}

export function Header({ activeTab = "new-trip", onTabChange }: HeaderProps) {
  const { isDark, toggle } = useDarkMode();

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
          <button
            onClick={() => onTabChange?.("new-trip")}
            className={
              activeTab === "new-trip"
                ? "text-primary border-b-2 border-primary font-bold pb-1 text-body-md"
                : "text-on-surface-variant hover:text-primary transition-colors text-body-md"
            }
          >
            New Trip
          </button>
          <button
            onClick={() => onTabChange?.("my-trips")}
            className={
              activeTab === "my-trips"
                ? "text-primary border-b-2 border-primary font-bold pb-1 text-body-md"
                : "text-on-surface-variant hover:text-primary transition-colors text-body-md"
            }
          >
            My Trips
          </button>
          <button className="text-on-surface-variant hover:text-primary transition-colors text-body-md">
            Profile
          </button>
        </nav>
        <div className="flex items-center gap-md">
          <button 
            onClick={toggle}
            className="w-10 h-10 rounded-full flex items-center justify-center text-on-surface-variant hover:bg-surface-variant transition-colors"
            title="Toggle Theme"
          >
            <span className="material-symbols-outlined text-[20px]">
              {isDark ? "light_mode" : "dark_mode"}
            </span>
          </button>
          <button 
            onClick={() => onTabChange?.("new-trip")}
            className="bg-primary-container text-on-primary-container px-lg py-sm rounded-lg text-label-md active:scale-95 transition-transform duration-150"
          >
            Create Trip
          </button>
        </div>
      </div>
    </header>
  );
}
