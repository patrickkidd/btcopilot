/** A recording kept in the device's own storage as it is made, so a reload,
 * a crash or the phone discarding the page never loses it (R-0955). One is
 * kept at a time. Its pieces of sound are stored under their order, and what
 * rebuilds it under ABOUT; it goes once the server has taken its upload or the
 * person discards or removes it. */

/** What rebuilds a kept recording, and where it was made. */
export interface About {
  kind: string;
  /** When it started, in milliseconds. */
  started: number;
  /** The running time when its last piece came in. */
  seconds: number;
  missed: number;
  diagram: number | null;
  /** The diagram's name, said when the recording is offered in another. */
  name: string;
}

export interface Found {
  about: About;
  pieces: ArrayBuffer[];
}

/** The small part of a storage the kept recording needs. */
export interface Shelf {
  put(key: IDBValidKey, value: unknown): Promise<void>;
  /** Everything stored, ordered by key. */
  entries(): Promise<[IDBValidKey, unknown][]>;
  clear(): Promise<void>;
}

const ABOUT = "about";
const DATABASE = "recording";
const SHELF = "kept";

const done = (request: IDBRequest | IDBTransaction) =>
  new Promise<void>((resolve, reject) => {
    const ok = () => resolve();
    const failed = () => reject(request.error);
    if (request instanceof IDBTransaction) {
      request.addEventListener("complete", ok);
      request.addEventListener("abort", failed);
    } else request.addEventListener("success", ok);
    request.addEventListener("error", failed);
  });

/** The device's IndexedDB. Private browsing or no storage at all refuses it
 * with a DOMException. */
export async function deviceShelf(): Promise<Shelf> {
  if (typeof indexedDB === "undefined") throw new DOMException("No storage on this device", "NotSupportedError");
  const opening = indexedDB.open(DATABASE, 1);
  opening.addEventListener("upgradeneeded", () => opening.result.createObjectStore(SHELF));
  await done(opening);
  const db = opening.result;
  const write = (act: (shelf: IDBObjectStore) => void) => {
    const tx = db.transaction(SHELF, "readwrite");
    act(tx.objectStore(SHELF));
    return done(tx);
  };
  return {
    put: (key, value) => write((shelf) => shelf.put(value, key)),
    clear: () => write((shelf) => shelf.clear()),
    entries: async () => {
      const shelf = db.transaction(SHELF).objectStore(SHELF);
      const keys = shelf.getAllKeys();
      const values = shelf.getAll();
      await done(values);
      return keys.result.map((key, i) => [key, values.result[i]]);
    },
  };
}

export class KeptRecording {
  /** Every write in the order asked, so the pieces and the time stay in step. */
  private queue: Promise<void> = Promise.resolve();
  private shelf: Promise<Shelf> | null = null;
  private about: About | null = null;
  private count = 0;
  /** The device would not store it; the recording goes on in memory only. */
  private failed = false;

  constructor(private readonly open: () => Promise<Shelf> = deviceShelf) {}

  private then(step: (shelf: Shelf) => Promise<void>): void {
    this.queue = this.queue
      .then(async () => {
        if (this.failed) return;
        this.shelf ??= this.open();
        await step(await this.shelf);
      })
      .catch((refused) => {
        if (!(refused instanceof DOMException)) throw refused;
        this.failed = true;
        this.shelf = null;
        console.warn(`The recording is kept in memory only, not on this device: ${refused.message}`);
      });
  }

  /** A new recording, in place of any kept before it. */
  begin(about: About): void {
    this.queue = this.queue.then(() => {
      this.failed = false;
    });
    this.about = about;
    this.count = 0;
    this.then(async (shelf) => {
      await shelf.clear();
      await shelf.put(ABOUT, about);
    });
  }

  /** A piece of sound, with the running time once it came in. */
  add(piece: Blob, seconds: number, missed: number, kind: string): void {
    const about = (this.about = { ...this.about!, seconds, missed, kind });
    const at = this.count++;
    this.then(async (shelf) => {
      await shelf.put(at, await piece.arrayBuffer());
      await shelf.put(ABOUT, about);
    });
  }

  /** Once the server has the upload, or the person discarded or removed it. */
  forget(): void {
    this.about = null;
    this.then((shelf) => shelf.clear());
  }

  /** Every write asked so far has landed or failed. */
  written(): Promise<void> {
    return this.queue;
  }

  /** The recording kept, if it holds any sound. */
  async find(): Promise<Found | null> {
    let about: About | null = null;
    const pieces: ArrayBuffer[] = [];
    this.then(async (shelf) => {
      for (const [key, value] of await shelf.entries())
        if (key === ABOUT) about = value as About;
        else pieces.push(value as ArrayBuffer);
    });
    await this.queue;
    return about && pieces.length ? { about, pieces } : null;
  }
}
