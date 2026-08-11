export default function Loading() {
  return (
    <div
      className="loading-page page-width"
      aria-label="Loading page"
      aria-live="polite"
    >
      <span className="loading-line loading-line--label" />
      <span className="loading-line loading-line--title" />
      <span className="loading-line loading-line--title loading-line--short" />
      <span className="loading-line loading-line--body" />
      <span className="loading-line loading-line--body loading-line--short" />
    </div>
  );
}
