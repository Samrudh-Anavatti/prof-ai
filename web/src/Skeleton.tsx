export function PageSkeleton({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="skeleton-page" role="status">
      <span className="visually-hidden">{label}</span>
      <span className="skeleton skeleton-title" />
      <span className="skeleton skeleton-line" />
      <span className="skeleton skeleton-line short" />
      <span className="skeleton skeleton-card" />
      <span className="skeleton skeleton-card" />
    </div>
  );
}
