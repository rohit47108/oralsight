import type { ReactNode, SVGProps } from "react";

export type ProductIconName =
  | "analytics"
  | "archive"
  | "document"
  | "home"
  | "review"
  | "settings"
  | "share"
  | "shield";

const paths: Record<ProductIconName, ReactNode> = {
  analytics: (
    <>
      <path d="M4 20V10m6 10V4m6 16v-7m4 7H2" />
    </>
  ),
  home: (
    <path d="M3.5 10.5 12 3l8.5 7.5v9a1.5 1.5 0 0 1-1.5 1.5h-4.5v-6h-5v6H5a1.5 1.5 0 0 1-1.5-1.5Z" />
  ),
  archive: (
    <>
      <path d="M4 7.5h16v12H4z" />
      <path d="M3 3h18v4.5H3zm6 9h6" />
    </>
  ),
  document: (
    <>
      <path d="M6 2.5h8l4 4V21H6z" />
      <path d="M14 2.5v4h4M9 12h6m-6 4h6" />
    </>
  ),
  share: (
    <>
      <circle cx="18" cy="5" r="2.5" />
      <circle cx="6" cy="12" r="2.5" />
      <circle cx="18" cy="19" r="2.5" />
      <path d="m8.3 10.8 7.4-4.5m-7.4 6.9 7.4 4.5" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path
        d="M19 13.5v-3l-2.2-.6a7 7 0 0 0-.7-1.6l1.2-2-2.1-2.1-2 1.2a7 7 0 0 0-1.6-.7L11 2.5H8l-.6 2.2a7 7 0 0 0-1.6.7l-2-1.2-2.1 2.1 1.2 2a7 7 0 0 0-.7 1.6L0 10.5v3l2.2.6a7 7 0 0 0 .7 1.6l-1.2 2 2.1 2.1 2-1.2a7 7 0 0 0 1.6.7l.6 2.2h3l.6-2.2a7 7 0 0 0 1.6-.7l2 1.2 2.1-2.1-1.2-2a7 7 0 0 0 .7-1.6z"
        transform="translate(2.5) scale(.79)"
      />
    </>
  ),
  review: (
    <>
      <path d="M5 3h14v18H5z" />
      <path d="M8.5 8h7m-7 4h7m-7 4h4" />
    </>
  ),
  shield: (
    <path d="M12 2.5 20 6v5.5c0 4.8-3.1 8.1-8 10-4.9-1.9-8-5.2-8-10V6Zm-3 9 2 2 4-4" />
  ),
};

export function ProductIcon({
  name,
  ...props
}: { name: ProductIconName } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
