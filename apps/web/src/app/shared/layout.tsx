import type { Metadata } from "next";
import type { ReactNode } from "react";

import { BrandMark } from "@/components/brand-mark";

export const metadata: Metadata = {
  robots: {
    index: false,
    follow: false,
    nocache: true,
    googleBot: {
      index: false,
      follow: false,
      noimageindex: true,
    },
  },
};

export default function SharedLayout({ children }: { children: ReactNode }) {
  return (
    <div className="shared-shell">
      <header className="shared-shell__header">
        <BrandMark />
        <span>View-only record</span>
      </header>
      <main id="main-content" className="shared-shell__main">
        {children}
      </main>
      <footer className="product-disclaimer">
        <strong>This result is not a diagnosis.</strong>
        <span>
          Use this shared record to support a professional conversation.
        </span>
      </footer>
    </div>
  );
}
