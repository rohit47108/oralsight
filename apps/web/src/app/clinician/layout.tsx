import { redirect } from "next/navigation";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { ProductGate } from "@/components/product-gate";
import { ProductShell } from "@/components/product-shell";
import { getProductContext, productHomeForRole } from "@/lib/product-auth";

export const metadata: Metadata = {
  robots: { index: false, follow: false, nocache: true },
};

export default async function ClinicianLayout({
  children,
}: {
  children: ReactNode;
}) {
  const context = await getProductContext();
  if (context.state !== "ready") return <ProductGate context={context} />;
  if (
    !new Set(["clinician_pending", "clinician", "admin"]).has(
      context.account.role,
    )
  ) {
    redirect(productHomeForRole(context.account.role));
  }
  return (
    <ProductShell
      area="clinician"
      identity={context.identity}
      role={context.account.role}
    >
      {children}
    </ProductShell>
  );
}
