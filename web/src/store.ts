import * as api from "./api";
import { Access, emptyTimeline, type Diagram, type Session, type Timeline } from "./types";

/** The diagram the page has open, held in one place (FD-366). One step opens a
 * diagram, the first load and every switch alike: it cancels whatever is still
 * coming for the one before, puts every screen back to empty, reads everything
 * about the new one by its id, and draws every screen from what came back.
 * Screens read the open diagram from here and never fetch it on their own. */

/** What a screen draws from, each part read by the diagram's id. */
export enum Part {
  /** The record: people, events, clusters, and the coach's questions. */
  Record = "record",
  /** The newest page of the family's thread. */
  Thread = "thread",
  /** The family's sittings, newest first. */
  Sittings = "sittings",
}

const EVERY = [Part.Record, Part.Thread, Part.Sittings];

export interface Opened {
  /** Null only for an account that has no diagram yet; its first words make
   * one, on the server. */
  diagram: Diagram | null;
  record: Timeline;
  thread: api.Said[];
  sittings: Session[];
}

/** A screen showing the open diagram: emptied the moment another one starts
 * opening, and drawn from the parts that changed once they are in. */
export interface View {
  reset(): void;
  draw(opened: Opened, parts: Part[]): void;
}

/** What the server put in the page, so the first open reads only the rest. */
export interface Seed {
  diagram: Diagram | null;
  thread: api.Said[];
}

const EMPTY: Opened = { diagram: null, record: emptyTimeline(), thread: [], sittings: [] };

export class Store {
  private opened: Opened = EMPTY;
  /** The diagram open or being opened. */
  private at: number | null = null;
  private views: View[] = [];
  private control = new AbortController();
  /** The running turn's stream, which belongs to the diagram it was said on. */
  private turn: EventSource | null = null;
  /** Counts opens, so whatever was asked for an earlier one is dropped. */
  private count = 0;

  watch(view: View): void {
    this.views.push(view);
  }

  current(): Opened {
    return this.opened;
  }

  /** The diagram open, or the one being opened, by id. */
  id(): number | null {
    return this.at;
  }

  /** An admin looking at another person's diagram: nothing is said, tapped
   * into the record or written (Patrick, 2026-10-01). */
  readOnly(): boolean {
    return this.opened.diagram?.access === Access.AdminView;
  }

  /** True while the diagram open when it was called is still the one open. */
  live(): () => boolean {
    const was = this.count;
    return () => this.count === was;
  }

  /** The one way a diagram is opened. False when another open overtook it. */
  async open(id: number | null, seed?: Seed): Promise<boolean> {
    const live = this.begin(id);
    const signal = this.control.signal;
    let read;
    try {
      read = await Promise.all([
        seed ? seed.diagram : api.selectDiagram(id!, signal),
        api.timeline(id, signal),
        seed ? seed.thread : api.thread(id, undefined, signal),
        api.sessionIndex(id, signal),
      ]);
    } catch (error) {
      if (error instanceof api.Dropped) return false;
      throw error;
    }
    if (!live()) return false;
    const [diagram, record, thread, sittings] = read;
    this.opened = { diagram, record, thread, sittings };
    this.draw(EVERY);
    return true;
  }

  /** Read parts of the open diagram again and draw them; false when another
   * diagram was opened before they came back. */
  async refresh(...parts: Part[]): Promise<boolean> {
    const read = await Promise.all(parts.map((part) => this.fetch(READ[part])));
    if (read.some((one) => one === null)) return false;
    this.update(Object.fromEntries(parts.map((part, i) => [KEY[part], read[i]])));
    return true;
  }

  /** Parts read elsewhere for the open diagram, drawn as if refreshed. */
  update(fresh: Partial<Opened>): void {
    this.opened = { ...this.opened, ...fresh };
    this.draw(EVERY.filter((part) => KEY[part] in fresh));
  }

  /** A request about the open diagram, cancelled if another is opened; null
   * when it was. */
  async fetch<T>(ask: (id: number | null, signal: AbortSignal) => Promise<T>): Promise<T | null> {
    const live = this.live();
    try {
      const answer = await ask(this.at, this.control.signal);
      return live() ? answer : null;
    } catch (error) {
      if (error instanceof api.Dropped) return null;
      throw error;
    }
  }

  /** The running turn's stream, closed when another diagram opens. */
  hold(turn: EventSource): void {
    this.turn = turn;
  }

  release(): void {
    this.turn?.close();
    this.turn = null;
  }

  private begin(id: number | null): () => boolean {
    this.count += 1;
    this.at = id;
    this.control.abort();
    this.control = new AbortController();
    this.release();
    this.opened = { ...EMPTY };
    for (const view of this.views) view.reset();
    return this.live();
  }

  private draw(parts: Part[]): void {
    for (const view of this.views) view.draw(this.opened, parts);
  }
}

const KEY: Record<Part, keyof Opened> = {
  [Part.Record]: "record",
  [Part.Thread]: "thread",
  [Part.Sittings]: "sittings",
};

const READ: Record<Part, (id: number | null, signal: AbortSignal) => Promise<unknown>> = {
  [Part.Record]: (id, signal) => api.timeline(id, signal),
  [Part.Thread]: (id, signal) => api.thread(id, undefined, signal),
  [Part.Sittings]: (id, signal) => api.sessionIndex(id, signal),
};

/** The page's one store. */
export const store = new Store();
