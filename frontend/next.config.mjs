/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  images: { unoptimized: true },
  // Single-page app; no per-route HTML needed.
  trailingSlash: false,
};

export default nextConfig;
