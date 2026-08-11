"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ProductIcon, type ProductIconName } from "@/components/product-icon";

export type ProductNavigationItem = {
  href: string;
  label: string;
  icon: ProductIconName;
};

export function ProductNav({
  label,
  items,
}: {
  label: string;
  items: readonly ProductNavigationItem[];
}) {
  const pathname = usePathname();
  return (
    <nav className="product-nav" aria-label={label}>
      {items.map((item) => {
        const current =
          pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={current ? "page" : undefined}
          >
            <ProductIcon name={item.icon} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
