import Link from "next/link";

import {
  DISCLAIMER,
  footerNavigation,
  primaryNavigation,
} from "@/content/site";

import { BrandMark } from "./brand-mark";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="disclaimer-band">
        <div className="page-width disclaimer-band__inner">
          <span className="disclaimer-band__mark" aria-hidden="true">
            i
          </span>
          <strong>{DISCLAIMER}</strong>
          <span>
            OralSight records and organizes observations for discussion with a
            qualified professional.
          </span>
        </div>
      </div>
      <div className="page-width footer-grid">
        <div className="footer-lead">
          <BrandMark />
          <p>A consistent way to document changes you can see.</p>
        </div>
        <nav aria-label="Product links">
          <p className="footer-heading">Product</p>
          {primaryNavigation.slice(0, 3).map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
        <nav aria-label="Trust links">
          <p className="footer-heading">Trust</p>
          {footerNavigation.map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
      <div className="page-width footer-bottom">
        <span>© {new Date().getFullYear()} OralSight</span>
        <span>Guided oral observation and comparison</span>
      </div>
    </footer>
  );
}
