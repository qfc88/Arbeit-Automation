/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // The home nginx terminates /api/* upstream-side, so the frontend just
  // calls relative /api/... and lets nginx route it to the FastAPI service.
  // In dev, NEXT_PUBLIC_API_URL can override.
};

export default nextConfig;
