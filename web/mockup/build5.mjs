#!/usr/bin/env node
/** Builds the case report gallery, version 5, as ONE self-contained HTML file.
 *
 *   node web/mockup/build5.mjs            (from the worktree root)
 *
 * Runs the Vite build of the version 5 entry (MOCKUP=1 with MOCKUP_ENTRY
 * mockup5.html; output in web/mockup/dist), then inlines the built script, the
 * built stylesheet and Patrick's case from the private corpus (the case file,
 * the page file and the questions file beside it) into
 * fd-corpus/design/fd336/gallery-v5.html. The case files are read here at build
 * time and never copied under the worktree. Version 4 (build.mjs) is untouched. */
import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, "..");
const dist = join(here, "dist");
const CASES = process.env.FD336_CASES ?? "/home/pstinson/btcopilot/btcopilot-sources/fd-corpus/design/fd336/cases";
const OUT = process.env.FD336_OUT ?? "/home/pstinson/btcopilot/btcopilot-sources/fd-corpus/design/fd336/gallery-v5.html";

execSync("npx vite build", { cwd: web, stdio: "inherit", env: { ...process.env, MOCKUP: "1", MOCKUP_ENTRY: "mockup5.html" } });

const assets = join(dist, "assets");
const files = readdirSync(assets);
const js = files.filter((f) => f.endsWith(".js"));
const css = files.filter((f) => f.endsWith(".css"));
if (js.length !== 1 || css.length !== 1) throw new Error(`expected one script and one stylesheet in ${assets}, found ${files.join(", ")}`);
const script = readFileSync(join(assets, js[0]), "utf8").replaceAll("</script", "<\\/script");
const style = readFileSync(join(assets, css[0]), "utf8");
if (style.includes("</style")) throw new Error("the stylesheet holds a closing style tag");

const read = (name) => {
  const path = join(CASES, name);
  if (!existsSync(path)) throw new Error(`missing case file ${path}`);
  return JSON.parse(readFileSync(path, "utf8"));
};
const cases = ["patrick"].map((name) => ({ file: read(`${name}.json`), page: read(`${name}.page.json`), questions: read(`${name}.questions.json`) }));
const json = JSON.stringify(cases).replaceAll("</script", "<\\/script").replaceAll("<!--", "<\\!--");

const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Case report mockups, version 5</title>
<link rel="icon" href="data:,">
<style id="app-css">
${style}
</style>
</head>
<body>
<main id="gallery"></main>
<script>window.__CASES__=${json};</script>
<script type="module" id="bundle">
${script}
</script>
</body>
</html>
`;

mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, html);
console.log(`wrote ${OUT} (${(html.length / 1024).toFixed(0)} KB)`);
