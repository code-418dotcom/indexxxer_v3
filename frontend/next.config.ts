import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Proxy /api/* to the FastAPI backend during development.
  // In production, Traefik handles this routing instead.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },

  // Allow serving thumbnails from the backend origin
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
        pathname: "/api/**",
      },
    ],
  },
};

export default nextConfig;
