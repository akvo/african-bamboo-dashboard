/** @type {import('next').NextConfig} */

const nextConfig = {
  skipTrailingSlashRedirect: true,
  devIndicators: false,
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        poll: 1000,
        aggregateTimeout: 300,
      };
    }
    return config;
  },
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
      {
        source: "/storage/attachments/:path*",
        destination:
          "http://127.0.0.1:8000/storage/attachments/:path*",
      },
      {
        source: "/admin/:path*/",
        destination: "http://127.0.0.1:8000/admin/:path*/",
      },
      {
        source: "/admin/:path*",
        destination: "http://127.0.0.1:8000/admin/:path*",
      },
      {
        source: "/static/:path*",
        destination: "http://127.0.0.1:8000/static/:path*",
      },
    ];
  },
};

export default nextConfig;
