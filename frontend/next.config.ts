import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output = a self-contained server.js with only the deps it
  // actually needs, copied into the runtime stage of frontend/Dockerfile
  // instead of the full node_modules tree. Required for that Dockerfile.
  output: "standalone",
};

export default nextConfig;
