export default function Home() {
  return (
    <main className="min-h-screen flex flex-col">
      <header className="border-b border-[var(--color-border-subtle)]">
        <div className="max-w-[var(--max-width-report)] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-2 h-2 rounded-full bg-[var(--color-accent)]" />
            <span className="font-serif text-base text-[var(--color-ink-primary)]">
              Spacebio Translator
            </span>
          </div>
          <span className="text-xs text-[var(--color-ink-tertiary)] font-mono">v0.1</span>
        </div>
      </header>

      <div className="flex-1 max-w-[var(--max-width-report)] mx-auto px-6 py-12 w-full">
        <div className="text-center py-20">
          <h1 className="font-serif text-3xl text-[var(--color-ink-primary)] mb-3">
            Translate biotech experiments for ISS deployment
          </h1>
          <p className="text-[var(--color-ink-secondary)] max-w-[var(--max-width-prose)] mx-auto leading-relaxed">
            Describe an experimental protocol. Get a multi-perspective compliance analysis
            from five specialized agents covering hardware, microgravity adaptation, safety,
            mission integration, and regulatory pathway.
          </p>
        </div>
      </div>
    </main>
  );
}
