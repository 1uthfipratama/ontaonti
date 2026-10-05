import type { MetadataRoute } from "next";

/** Installable app ("Add to home screen" / "Install Onti Erlina"). */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Onti Erlina",
    short_name: "Onti Erlina",
    description: "Kotak masuk dan pendamping TBC untuk staf",
    start_url: "/inbox",
    scope: "/",
    display: "standalone",
    background_color: "#f1f4f9",
    theme_color: "#4b61dc",
    lang: "id",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
