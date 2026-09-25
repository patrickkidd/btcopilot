import { beforeEach, vi } from "vitest";
import { Questions } from "../src/questions";
import type { AskedQuestion } from "../src/types";

/** Just enough of the drawer's list for its own taps: the clicks it listens
 * for, rows that know which item they hold, and the requests it makes. */

export const fetched = vi.fn(async () => ({ ok: true, status: 204, text: async () => "" }));

beforeEach(() => {
  fetched.mockClear();
  vi.stubGlobal("fetch", fetched);
  vi.stubGlobal("document", { querySelector: () => null });
});

/** The request the tap sent: where to, how, and with what. */
export const sentAt = (n = 0) => {
  const [url, init] = fetched.mock.calls[n] as unknown as [string, RequestInit];
  return { url, method: init.method, body: JSON.parse(init.body as string) };
};

export function drawer(asked: AskedQuestion[], busy = false) {
  const heard: Record<string, (e: unknown) => void> = {};
  const body = {
    innerHTML: "",
    scrollTop: 0,
    addEventListener: (kind: string, fn: (e: unknown) => void) => {
      heard[kind] = fn;
    },
  } as unknown as HTMLElement;
  const handlers = {
    onChip: vi.fn(),
    onAsked: vi.fn(),
    onDismissed: vi.fn(),
    busy: () => busy,
    say: vi.fn(),
    record: vi.fn(),
  };
  const list = new Questions(body, handlers);
  list.show(asked);
  /** A tap on the part of a row that `on` names; `data` is that part's own. */
  const click = async (id: string, on: string, data: Record<string, string> = {}) => {
    const classes = new Set<string>();
    const row = {
      dataset: { q: id },
      classList: {
        contains: (c: string) => classes.has(c),
        add: (...c: string[]) => c.forEach((one) => classes.add(one)),
        remove: (...c: string[]) => c.forEach((one) => classes.delete(one)),
      },
      insertAdjacentHTML: () => {},
      querySelector: () => null,
    };
    const part = { dataset: data };
    const target = {
      closest: (sel: string) => {
        const any = sel.split(",").map((one) => one.trim());
        if (any.includes(on)) return any.some((one) => one === ".qrow" || one === ".irow") ? row : part;
        return any.includes(".qrow") ? row : null;
      },
    };
    heard.click({ target });
    // the tap's own requests settle before anything is looked at
    await new Promise((settle) => setTimeout(settle, 0));
  };
  return { list, handlers, click };
}
