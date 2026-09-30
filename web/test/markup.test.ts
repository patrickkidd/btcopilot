import { expect, it } from "vitest";
import { markup } from "../src/markup";

// R-0017
it("draws bold, italics and line breaks, and leaves a snake_case word alone", () => {
  expect(markup("This has **bold**, _italics_ and a_b_c.\nA second line.")).toBe(
    "This has <strong>bold</strong>, <em>italics</em> and a_b_c.<br>A second line.",
  );
});

// R-0017
it("makes a secure or same-site link that opens in a new tab, and leaves any other link as words", () => {
  expect(markup("See [the **pages**](https://x.org/a_b_c) or [here](/app/theory).")).toBe(
    'See <a href="https://x.org/a_b_c" target="_blank" rel="noopener">the <strong>pages</strong></a>' +
      ' or <a href="/app/theory" target="_blank" rel="noopener">here</a>.',
  );
  expect(markup("[x](javascript:alert(1)) [y](http://x.org) [z](//x.org)")).toBe(
    "[x](javascript:alert(1)) [y](http://x.org) [z](//x.org)",
  );
});

// R-0017
it("shows an injected script tag as words, never as HTML", () => {
  expect(markup('<script>alert("hi")</script> **<b>x</b>**')).toBe(
    "&lt;script&gt;alert(&quot;hi&quot;)&lt;/script&gt; <strong>&lt;b&gt;x&lt;/b&gt;</strong>",
  );
  expect(markup('[a](https://x.org/"><script>)')).toBe(
    '<a href="https://x.org/&quot;&gt;&lt;script&gt;" target="_blank" rel="noopener">a</a>',
  );
});
