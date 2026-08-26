import { redirect } from "next/navigation";

import { getProductContext, productHomeForAccount } from "@/lib/product-auth";

export default async function ClinicianEntryPage() {
  const context = await getProductContext();
  if (context.state === "ready")
    redirect(productHomeForAccount(context.account));
  return null;
}
