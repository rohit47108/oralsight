import type { ReactNode } from "react";

import { BrandMark } from "@/components/brand-mark";
import type { ProductIconName } from "@/components/product-icon";
import { ProductNav } from "@/components/product-nav";
import type { ViewerIdentity } from "@/lib/product-auth";
import type { UserRole } from "@/lib/platform-api";

type NavigationItem = {
  href: string;
  label: string;
  icon: ProductIconName;
};

const patientNavigation: readonly NavigationItem[] = [
  { href: "/app/overview", label: "Overview", icon: "home" },
  { href: "/app/scans", label: "Scans", icon: "archive" },
  { href: "/app/reports", label: "Reports", icon: "document" },
  { href: "/app/share", label: "Sharing", icon: "share" },
  { href: "/app/settings", label: "Account", icon: "settings" },
];

const clinicianNavigation: readonly NavigationItem[] = [
  { href: "/clinician/reviews", label: "Review queue", icon: "review" },
  { href: "/clinician/verification", label: "Verification", icon: "shield" },
  { href: "/clinician/settings", label: "Account", icon: "settings" },
];

const adminNavigation: readonly NavigationItem[] = [
  { href: "/clinician/admin", label: "Verification queue", icon: "shield" },
  {
    href: "/clinician/admin/analytics",
    label: "Product use",
    icon: "analytics",
  },
  { href: "/clinician/settings", label: "Account", icon: "settings" },
];

export function ProductShell({
  area,
  identity,
  role,
  children,
}: {
  area: "patient" | "clinician" | "shared";
  identity: ViewerIdentity;
  role: UserRole;
  children: ReactNode;
}) {
  const navigation =
    area === "clinician"
      ? role === "admin"
        ? adminNavigation
        : clinicianNavigation
      : patientNavigation;
  const areaLabel =
    area === "clinician"
      ? "Clinical review"
      : area === "shared"
        ? "Shared record"
        : "My Stoma3D";

  return (
    <div className={`product-shell product-shell--${area}`}>
      <aside className="product-sidebar">
        <div className="product-sidebar__brand">
          <BrandMark />
          <span>{areaLabel}</span>
        </div>
        {area !== "shared" ? (
          <ProductNav label={`${areaLabel} navigation`} items={navigation} />
        ) : null}
        <div className="product-sidebar__account">
          <span className="account-avatar" aria-hidden="true">
            {identity.displayName.slice(0, 1).toUpperCase()}
          </span>
          <div>
            <strong>{identity.displayName}</strong>
            <span>{role.replaceAll("_", " ")}</span>
          </div>
          <a href="/auth/logout">Sign out</a>
        </div>
      </aside>
      <div className="product-stage">
        <header className="product-topbar">
          <BrandMark />
          <span>{areaLabel}</span>
          <a href="/auth/logout">Sign out</a>
        </header>
        <main id="main-content" className="product-main">
          {children}
        </main>
        <footer className="product-disclaimer">
          <strong>This result is not a diagnosis.</strong>
          <span>
            Use Stoma3D records to support a professional conversation.
          </span>
        </footer>
      </div>
    </div>
  );
}
