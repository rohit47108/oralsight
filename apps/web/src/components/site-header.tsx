import Link from "next/link";

import { primaryNavigation } from "@/content/site";

import { BrandMark } from "./brand-mark";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="site-header__inner page-width">
        <BrandMark />
        <nav className="desktop-nav" aria-label="Primary navigation">
          {primaryNavigation.map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="header-actions">
          <Link className="button button--compact" href="/signin">
            Open OralSight
          </Link>
        </div>
        <details className="mobile-menu">
          <summary aria-label="Open navigation">
            <span />
            <span />
          </summary>
          <nav aria-label="Mobile navigation">
            {primaryNavigation.map((item) => (
              <Link key={item.href} href={item.href}>
                {item.label}
              </Link>
            ))}
            <Link href="/security">Security</Link>
            <Link href="/accessibility">Accessibility</Link>
            <Link className="button" href="/signin">
              Open OralSight
            </Link>
          </nav>
        </details>
      </div>
    </header>
  );
}
