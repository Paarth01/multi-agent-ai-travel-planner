export function Footer({ note }: { note?: string }) {
  return (
    <footer className="bg-surface-container-low w-full mt-auto border-t border-surface-variant">
      <div className="flex flex-col md:flex-row justify-between items-center py-xl px-margin-mobile md:px-margin-desktop max-w-[1440px] mx-auto gap-lg">
        <div className="flex flex-col items-center md:items-start gap-xs">
          <span className="text-headline-sm font-bold text-on-surface">TripSync AI</span>
          <p className="text-body-sm text-on-surface-variant">© 2024 TripSync AI. All rights reserved.</p>
          {note && <p className="text-body-sm text-tertiary mt-xs">{note}</p>}
        </div>
        <div className="flex gap-lg">
          <a className="text-body-sm text-on-surface-variant hover:text-primary transition-colors" href="#">
            Support
          </a>
          <a className="text-body-sm text-on-surface-variant hover:text-primary transition-colors" href="#">
            Privacy Policy
          </a>
          <a className="text-body-sm text-on-surface-variant hover:text-primary transition-colors" href="#">
            Terms of Service
          </a>
        </div>
      </div>
    </footer>
  );
}
