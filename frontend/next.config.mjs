/** @type {import('next').NextConfig} */

const nextConfig = {
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      {
        source: "/api/docs",
        destination: "http://127.0.0.1:8000/api/docs/",
      },
      {
        source: "/api/schema",
        destination: "http://127.0.0.1:8000/api/schema/",
      },
      {
        source: "/api/:path((?!docs$)(?!schema$).*)",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
