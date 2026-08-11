import type { Metadata, Viewport } from "next";
import { connection } from "next/server";

import { SiteChrome } from "@/components/site-chrome";

import "./globals.css";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://oralsight.org";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "OralSight - Document changes you can see",
    template: "%s - OralSight",
  },
  description:
    "OralSight guides a consistent eight-region mouth scan, organizes non-diagnostic observations, and prepares a report you control.",
  applicationName: "OralSight",
  category: "health",
  openGraph: {
    type: "website",
    siteName: "OralSight",
    title: "OralSight - Document changes you can see",
    description:
      "A consistent eight-region capture path for private, non-diagnostic oral observations.",
  },
  twitter: {
    card: "summary",
    title: "OralSight",
    description: "Document changes you can see, one consistent scan at a time.",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7faf8" },
    { media: "(prefers-color-scheme: dark)", color: "#091719" },
  ],
};

const directionContract = `<!--
THESIS: The fixed eight-region capture path is the page itself; it refuses the centered health-app hero and generic feature-card grid.
OWN-WORLD: Porcelain paper, graphite type, mineral teal actions, fine rules, instrument-like controls, and amber only for attention.
STORY: Consent leads to consistent capture, honest observation review, and sharing the user controls.
FIRST VIEWPORT: A numbered rail anchors the left, direct promise and phone capture occupy the center, and the eight-region guide resolves the right. The main action sits beside the promise.
FORM: Guided-scan editorial field, selected direction B, asymmetric stage with responsive stacked chapters; approved visual seed is the stored public direction comp.
-->`;

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // A fresh request is required so Next.js can attach the proxy-generated CSP
  // nonce to its framework and hydration scripts.
  await connection();
  return (
    <html lang="en">
      <body>
        <div
          className="direction-contract"
          aria-hidden="true"
          dangerouslySetInnerHTML={{ __html: directionContract }}
        />
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <SiteChrome>{children}</SiteChrome>
      </body>
    </html>
  );
}
