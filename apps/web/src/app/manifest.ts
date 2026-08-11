import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "OralSight",
    short_name: "OralSight",
    description:
      "A consistent eight-region capture path for non-diagnostic oral observations.",
    start_url: "/",
    display: "standalone",
    background_color: "#f7faf8",
    theme_color: "#096d67",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
      },
    ],
  };
}
