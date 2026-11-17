/**
 * Sub-path the app is served under (Next.js `basePath`), or '' at the URL root.
 * next/link and the router add it automatically; plain URLs (public assets in
 * next/image `src`, `window.location`) need `withBasePath`.
 */
export const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export const withBasePath = (path: string) => `${basePath}${path}`;
