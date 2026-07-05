import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // D-23: static export — the deployed dashboard is plain files served by the API (D-26).
  output: "export",
};

export default nextConfig;
