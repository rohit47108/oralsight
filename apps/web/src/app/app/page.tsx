import { redirect } from "next/navigation";

import { getProductContext, productHomeForRole } from "@/lib/product-auth";

export default async function ProductEntryPage() {
  const context = await getProductContext();
  if (context.state === "ready")
    redirect(productHomeForRole(context.account.role));
  return null;
}
