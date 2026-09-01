import type { MetadataRoute } from "next";

const routes = [
  "",
  "/how-it-works",
  "/privacy",
  "/security",
  "/for-professionals",
  "/accessibility",
  "/research",
  "/calibration",
] as const;

export default function sitemap(): MetadataRoute.Sitemap {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? "https://stoma3d.org";

  return routes.map((route) => ({
    url: `${siteUrl}${route}`,
    changeFrequency: route === "" ? "monthly" : "yearly",
    priority: route === "" ? 1 : 0.7,
  }));
}
