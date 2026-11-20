import { expect, it } from "vitest";
import { ACCEPT } from "../src/recording";

// R-0950
it("lets the iPhone's Files picker choose a recording by its file ending, any audio type still allowed", () => {
  const kinds = ACCEPT.split(",");
  for (const kind of [
    ".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".opus", ".wma", ".amr", ".aif", ".aiff", ".caf", ".qta",
    "audio/*",
  ])
    expect(kinds).toContain(kind);
});
