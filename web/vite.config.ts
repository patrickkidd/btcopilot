/// <reference types="vitest" />
import { existsSync, readFileSync } from "node:fs";
import { request as ask } from "node:http";
import { defineConfig, type Plugin, type ProxyOptions } from "vite";

// Flask serves the bundle through the personal blueprint's static folder, and
// names the entry files itself in the page template, so the output names are
// fixed rather than hashed.
const BASE = "/personal/static/web/";

/** The sandbox this dev server borrows its server from. */
const FLASK = process.env.FLASK_URL ?? "http://127.0.0.1:8890";

/** Everything the server owns. The page itself is not here: it is served from
 * this repo so an edit shows on refresh, with the two things only the server
 * knows grafted into it. `/personal/static/web` is left out on purpose — that
 * is where this dev server's own modules live. */
const SERVER_PATHS = [
  "^/personal/(?!static/web)",
  "/review",
  "/training",
  "/static",
];

const CERT_DIR = process.env.DEV_CERT_DIR ?? new URL("./certs/", import.meta.url).pathname;
const DEV_HOST = process.env.DEV_HOST ?? "turin.local";
function certs(): { key: Buffer; cert: Buffer } | undefined {
  const key = `${CERT_DIR}/${DEV_HOST}.key`;
  if (!existsSync(key)) return undefined;
  return { key: readFileSync(key), cert: readFileSync(`${CERT_DIR}/${DEV_HOST}.crt`) };
}

const proxy: Record<string, ProxyOptions> = Object.fromEntries(
  // the Host header is left alone so the server builds its links, and sets its
  // cookies, for the address the reader actually typed
  SERVER_PATHS.map((path) => [path, { target: FLASK, changeOrigin: false }]),
);

/** Ask the server for the page as this reader. Written against node's own
 * client rather than fetch because the Host header has to survive: the server
 * builds its sign-in links and sets its cookies from it, so a request that
 * arrived at this machine's network name must reach the server saying so. */
function fromServer(headers: Record<string, unknown>) {
  const to = new URL(`${FLASK}/personal/`);
  return new Promise<{
    status: number;
    body: string;
    cookies: string[];
    location: string | undefined;
  }>((done, fail) => {
    const call = ask(
      {
        host: to.hostname,
        port: to.port,
        path: to.pathname,
        headers: {
          cookie: (headers.cookie as string) ?? "",
          host: (headers.host as string) ?? to.host,
        },
      },
      (answer) => {
        let body = "";
        answer.setEncoding("utf8");
        answer.on("data", (part) => (body += part));
        answer.on("end", () =>
          done({
            status: answer.statusCode ?? 0,
            body,
            cookies: answer.headers["set-cookie"] ?? [],
            location: answer.headers.location,
          }),
        );
      },
    );
    call.on("error", fail);
    call.end();
  });
}

/** Serve the app's own page from the repo while the server still supplies the
 * CSRF token and the session to open on. Without this the dev server would
 * hand back the built bundle's page and nothing would reload. */
function page(): Plugin {
  return {
    name: "fd-dev-page",
    apply: "serve",
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        const url = (request.url ?? "").split("?")[0];
        if (url !== "/personal/" && url !== "/personal") return next();
        const from = await fromServer(request.headers);
        for (const cookie of from.cookies) response.appendHeader("Set-Cookie", cookie);
        if (from.status !== 200) {
          // signed out, or the server said something this cannot dress up
          response.statusCode = from.status;
          if (from.location) response.setHeader("Location", from.location);
          response.end(from.body);
          return;
        }
        const served = from.body;
        const head = [...served.matchAll(/<meta name="csrf-token"[^>]*>|<script>window\.BOOTSTRAP=.*?<\/script>/gs)]
          .map((match) => match[0])
          .join("");
        if (!head)
          throw new Error("the server's page carried no CSRF token or session");
        const here = readFileSync(new URL("./index.html", import.meta.url), "utf8");
        const html = await server.transformIndexHtml(
          request.url ?? "/personal/",
          here.replace("</head>", head + "</head>"),
        );
        response.setHeader("Content-Type", "text/html; charset=utf-8");
        response.end(html);
      });
    },
  };
}

export default defineConfig({
  base: BASE,
  plugins: [
    page(),
    {
      // iOS only offers to install the dev CA when it arrives as a certificate.
      name: "dev-ca-type",
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (!req.url?.endsWith("/dev-ca.crt")) return next();
          res.setHeader("Content-Type", "application/x-x509-ca-cert");
          res.end(readFileSync(`${CERT_DIR}/dev-ca.crt`));
        });
      },
    },
  ],
  build: {
    outDir: "../btcopilot/personal/static/web",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "app.js",
        chunkFileNames: "app-[name].js",
        assetFileNames: "app.[ext]",
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 8891,
    // Face ID sign-in needs https off localhost. devcerts.sh makes a dev CA
    // and a certificate it signed, outside git; DEV_CERT_DIR says where, and a
    // phone trusts the CA once by installing /dev-ca.crt from that directory.
    https: certs(),
    strictPort: true,
    // the review is opened at this machine's name on the network, not at
    // localhost, and the dev server turns away a host it was not told about
    // DEV_HOST is the bare name a phone opens (turin, R-0290); without it the
    // live-reload socket is refused with a 400 and an open page never refreshes
    allowedHosts: [DEV_HOST, "turin.local", "localhost", ".local"],
    proxy,
  },
  // Playwright owns tests/visual; vitest owns the pure unit tests only.
  test: { include: ["test/**/*.test.ts"] },
});
