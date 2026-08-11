import Link from "next/link";

export function BrandMark() {
  return (
    <Link className="brand-mark" href="/" aria-label="OralSight home">
      <svg
        className="brand-mark__symbol"
        viewBox="0 0 32 32"
        aria-hidden="true"
      >
        <circle
          cx="16"
          cy="16"
          r="10.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
        />
        <path
          d="M16 3.5a12.5 12.5 0 0 1 9.1 3.9l-4.4 3.9A6.7 6.7 0 0 0 16 9.5Z"
          fill="currentColor"
        />
        <path
          d="M28.5 16a12.5 12.5 0 0 1-3.9 9.1l-3.9-4.4a6.7 6.7 0 0 0 1.8-4.7Z"
          fill="currentColor"
          opacity=".72"
        />
        <path
          d="M16 28.5a12.5 12.5 0 0 1-9.1-3.9l4.4-3.9a6.7 6.7 0 0 0 4.7 1.8Z"
          fill="currentColor"
          opacity=".52"
        />
        <path
          d="M3.5 16a12.5 12.5 0 0 1 3.9-9.1l3.9 4.4A6.7 6.7 0 0 0 9.5 16Z"
          fill="currentColor"
          opacity=".34"
        />
      </svg>
      <span>OralSight</span>
    </Link>
  );
}
