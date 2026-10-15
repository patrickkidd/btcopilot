import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

const source = (name: string) => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");

// R-0711
it("leaves the chat screen with no picture controller of its own", () => {
  const main = source("main.ts");
  expect(main).not.toContain("new Picture(");
  expect(main).toContain("new Lens(");
});

// R-0711
it("keeps one width at which the app widens", () => {
  const all = ["main.ts", "pro.ts", "viewport.ts", "lens.ts", "casereport.ts"].map(source).join("\n");
  expect(all.match(/min-width: 840px/g)).toHaveLength(1);
});

// R-0850
it("opens a cluster's view one way, from its info button and from a chip naming it, its view counted when shown", () => {
  const lens = source("lens.ts");
  expect(lens.match(/picture\.about\(\)/g)).toHaveLength(1);
  expect(lens).toMatch(/Feature\.PictureInfo\);\s*this\.about\(\);/);
  expect(lens).toMatch(/this\.picture\.about\(\);\s*if \(this\.picture\.aboutOpen\(\)\) this\.hooks\.track\(VIEW_FEATURES\[storedView\(\)\]\)/);
  const report = source("casereport.ts");
  expect(report).toContain("void open.then(() => this.lens.about());");
  expect(report).not.toContain("picture.about(");
});

// R-0460
it("lays a cluster's about page over the case report as over the chat, held to the screen", () => {
  const page = readFileSync(new URL("../index.html", import.meta.url), "utf8");
  expect(page).toContain('<div class="view" id="case-view"></div>');
  expect(page).not.toContain("grows");
  expect(source("picture.ts")).toMatch(/private card\(markup: string\): void \{\s*this\.laid = \{ zones: \[\], rows: \[\] \};\s*this\.pin\(PIC_H\);/);
  expect(source("picture.ts")).toContain("card.style.maxHeight = `${window.innerHeight - this.host.getBoundingClientRect().top}px`;");
  expect(source("theme.css")).toMatch(/\.view \.card \{[^}]*overflow-x: hidden;\s*overflow-y: auto;/);
});

// R-0460
it("keeps the cards still on the screen while a cluster chip opens the folded line under its view", () => {
  const report = source("casereport.ts");
  expect(report).toMatch(/if \(cluster && chip\.kind === ChipKind\.Cluster\) \{\s*const open = this\.openOver\(\);/);
  expect(report).toContain("b.scrollTop = from + b.getBoundingClientRect().top - top;");
  expect(report).toContain("if (pic.getAnimations().length) requestAnimationFrame(keep);");
});
