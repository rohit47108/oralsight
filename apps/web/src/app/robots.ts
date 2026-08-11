import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://oralsight.org";

  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/app", "/auth/", "/clinician", "/shared", "/signin"],
    },
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
