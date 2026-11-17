import type { NextConfig } from 'next';

// Optional sub-path (e.g. "/annotaise") when the app is served beneath a proxy mount.
// Read at build time; NEXT_PUBLIC_ so client code can prefix plain asset URLs.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

const nextConfig: NextConfig = {
  basePath,
};

export default nextConfig;
