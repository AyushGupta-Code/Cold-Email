interface EmptyStateProps {
  warnings: string[];
}

export function EmptyState({ warnings }: EmptyStateProps) {
  return (
    <section className="panel p-6 md:p-8">
      <h2 className="font-display text-2xl text-ink">No contacts returned</h2>
      <p className="mt-3 max-w-3xl text-sm text-slatewarm">
        Common causes are sparse public recruiter pages, limited US-based evidence in search snippets, or search engines throttling
        lightweight requests.
      </p>
      {warnings.length ? (
        <div className="mt-5 rounded-3xl border border-slate-200 bg-slate-50 p-5">
          <h3 className="font-display text-lg">What the backend reported</h3>
          <ul className="mt-3 space-y-2 text-sm text-slatewarm">
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

