/** The family fragment: one person in the middle, their parents' bond above,
 * their own bond or bonds beside, the children under each bond. Fixed template
 * positions, no search, no crossing avoidance. Every measure is a fraction of
 * `u`, the person box, exactly as doc/chat-first/FRAGMENT_CONVENTIONS.md sets
 * it out; where that sheet leaves a rule open the choice is an Options field. */

export enum Sex {
  Male = "male",
  Female = "female",
  Miscarriage = "miscarriage",
  Abortion = "abortion",
  Unknown = "unknown",
}

export enum Kind {
  Birth = "birth",
  Death = "death",
  Adopted = "adopted",
  Married = "married",
  Bonded = "bonded",
  Separated = "separated",
  Divorced = "divorced",
}

export interface FragPerson {
  id: number;
  name: string | null;
  gender: string | null;
  /** The pair bond they are a child of, as the record holds it. */
  parents: number | null;
}

export interface FragBond {
  id: number;
  person_a: number | null;
  person_b: number | null;
  married: boolean | null;
}

export interface FragEvent {
  kind: string;
  person: number | null;
  spouse: number | null;
  dateTime: string | null;
}

export interface Fragment {
  center: number;
  people: FragPerson[];
  bonds: FragBond[];
  events: FragEvent[];
  /** Siblings born together, by person id. The record keeps no such field. */
  twins?: number[][];
  /** People and bonds the record is unsure about, drawn faint. */
  unsurePeople?: number[];
  unsureBonds?: number[];
  /** Children whose parents' bond is not in the record. */
  loose?: number[];
  /** People the record has adopted into a bond rather than born into it, when
   * no adoption event carries it. */
  adopted?: number[];
  /** What the fragment asks about, by person id: an amber question mark. */
  ask?: number[];
}

/** The spec draws a "?" inside the unknown-gender shape; the code draws none. */
export enum UnknownMark {
  None = "none",
  Question = "question",
}

/** The code points the miscarriage triangle up; the spec says down. */
export enum Apex {
  Up = "up",
  Down = "down",
}

/** With no custody recorded the code draws vertical slashes; the spec leans them. */
export enum Slash {
  Vertical = "vertical",
  Diagonal = "diagonal",
}

/** The code rises the twins' shared line a fixed 0.34u above them; the spec puts
 * it midway to the parents' bar. */
export enum TwinBar {
  Fixed = "fixed",
  Midpoint = "midpoint",
}

/** The code dashes an adopted child's line; Patrick's stated preference is solid
 * to every parent, with dashes kept for chosen parents. */
export enum AdoptLine {
  Dashed = "dashed",
  Solid = "solid",
}

export enum Side {
  MaleLeft = "male-left",
  OlderLeft = "older-left",
  RecordOrder = "record-order",
}

export enum BondOrder {
  EarliestNearest = "earliest-nearest",
  LatestNearest = "latest-nearest",
}

export enum Single {
  HalfU = "half-u",
  Ghost = "ghost",
  NoStub = "no-stub",
}

export enum Unnamed {
  Faint = "faint",
  Dashes = "dashes",
  Asked = "asked",
}

export enum Loose {
  Stub = "stub",
  AskOnly = "ask-only",
  GhostBond = "ghost-bond",
}

export enum NameFit {
  Ellipsis = "ellipsis",
  TwoLines = "two-lines",
  Shrink = "shrink",
}

export interface Options {
  u: number;
  unknownMark: UnknownMark;
  apex: Apex;
  slash: Slash;
  twinBar: TwinBar;
  adoptLine: AdoptLine;
  side: Side;
  bondOrder: BondOrder;
  single: Single;
  unnamed: Unnamed;
  loose: Loose;
  nameFit: NameFit;
  /** Centre to centre, in person boxes. */
  siblingGap: number;
  generationGap: number;
  partnerGap: number;
}

export const defaults: Options = {
  u: 44,
  unknownMark: UnknownMark.None,
  apex: Apex.Up,
  slash: Slash.Vertical,
  twinBar: TwinBar.Fixed,
  adoptLine: AdoptLine.Dashed,
  side: Side.MaleLeft,
  bondOrder: BondOrder.EarliestNearest,
  single: Single.HalfU,
  unnamed: Unnamed.Faint,
  loose: Loose.Stub,
  nameFit: NameFit.Ellipsis,
  siblingGap: 2,
  generationGap: 2,
  partnerGap: 2,
};

const STROKE = 0.03;
const DEPTH = 0.45;
const INDEX_GROW = 0.1;
const SLASH_RIGHT = 0.75;
const SLASH_RISE = 0.4;
const SLASH_DROP = 0.15;
const SLASH_STEP = 0.1;
const SLASH_LEAN = 0.2;
const TWIN_RISE = 0.34;
const TICK = 0.3;
const NAME_SIZE = 0.25;
const AGE_SIZE = 0.3;
const NAME_DROP = 0.78;
const CHAR = 0.53;

type At = { p: FragPerson; x: number; y: number; index: boolean; faint: boolean };

const esc = (text: string) =>
  text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

const num = (value: number) => (Math.round(value * 100) / 100).toString();

const year = (date: string | null | undefined) =>
  date ? Number(date.slice(0, 4)) : null;

const sexOf = (p: FragPerson): Sex =>
  p.gender && (Object.values(Sex) as string[]).includes(p.gender)
    ? (p.gender as Sex)
    : Sex.Unknown;

const nameRoom = (gap: number) => gap;

/** The given name only, on one line, cut to the box width plus one sibling gap. */
export const fitName = (
  name: string,
  fit: NameFit,
  gap: number,
  size: number,
): { lines: string[]; size: number } => {
  const given = [...name.trim().split(/\s+/)[0]];
  const room = nameRoom(gap);
  const max = Math.max(3, Math.floor(room / (size * CHAR)));
  if (given.length <= max) return { lines: [given.join("")], size };
  if (fit === NameFit.TwoLines) {
    const half = Math.ceil(given.length / 2);
    return {
      lines: [given.slice(0, half).join(""), given.slice(half).join("")],
      size,
    };
  }
  if (fit === NameFit.Shrink) {
    const shrunk = Math.max(size * 0.6, room / (given.length * CHAR));
    return { lines: [given.join("")], size: shrunk };
  }
  return { lines: [given.slice(0, max - 1).join("") + "…"], size };
};

class Draw {
  parts: string[] = [];
  min = { x: 0, y: 0 };
  max = { x: 0, y: 0 };

  seen(x: number, y: number) {
    this.min.x = Math.min(this.min.x, x);
    this.min.y = Math.min(this.min.y, y);
    this.max.x = Math.max(this.max.x, x);
    this.max.y = Math.max(this.max.y, y);
  }

  add(markup: string) {
    this.parts.push(markup);
  }

  line(
    d: string,
    opts: { faint?: boolean; dashed?: boolean; flat?: boolean; cls?: string } = {},
  ) {
    const cap = opts.flat ? "butt" : "round";
    this.add(
      `<path class="${opts.cls ?? "frag-line"}" d="${d}" fill="none" ` +
        `stroke="var(--${opts.faint ? "faint" : "ink"})" stroke-width="${num(STROKE)}" ` +
        `stroke-linecap="${cap}" stroke-linejoin="round"` +
        (opts.dashed ? ` stroke-dasharray="${num(0.12)} ${num(0.09)}"` : "") +
        ` />`,
    );
  }

  text(
    words: string,
    x: number,
    y: number,
    size: number,
    colour: string,
    cls: string,
  ) {
    this.add(
      `<text class="${cls}" x="${num(x)}" y="${num(y)}" font-size="${num(size)}" ` +
        `text-anchor="middle" fill="var(--${colour})" stroke="var(--panel)" ` +
        `stroke-width="${num(STROKE * 3)}" paint-order="stroke">${esc(words)}</text>`,
    );
  }
}

const shapePath = (sex: Sex, x: number, y: number, half: number, apex: Apex) => {
  if (sex === Sex.Miscarriage || sex === Sex.Abortion) {
    return apex === Apex.Up
      ? `M ${num(x)} ${num(y - half)} L ${num(x + half)} ${num(y + half)} ` +
          `L ${num(x - half)} ${num(y + half)} Z`
      : `M ${num(x - half)} ${num(y - half)} L ${num(x + half)} ${num(y - half)} ` +
          `L ${num(x)} ${num(y + half)} Z`;
  }
  if (sex === Sex.Female) {
    return (
      `M ${num(x - half)} ${num(y)} a ${num(half)} ${num(half)} 0 1 0 ${num(half * 2)} 0 ` +
      `a ${num(half)} ${num(half)} 0 1 0 ${num(-half * 2)} 0 Z`
    );
  }
  if (sex === Sex.Male) {
    return (
      `M ${num(x - half)} ${num(y - half)} H ${num(x + half)} V ${num(y + half)} ` +
      `H ${num(x - half)} Z`
    );
  }
  const r = half * 0.8;
  return (
    `M ${num(x - half + r)} ${num(y - half)} H ${num(x + half - r)} ` +
    `a ${num(r)} ${num(r)} 0 0 1 ${num(r)} ${num(r)} V ${num(y + half - r)} ` +
    `a ${num(r)} ${num(r)} 0 0 1 ${num(-r)} ${num(r)} H ${num(x - half + r)} ` +
    `a ${num(r)} ${num(r)} 0 0 1 ${num(-r)} ${num(-r)} V ${num(y - half + r)} ` +
    `a ${num(r)} ${num(r)} 0 0 1 ${num(r)} ${num(-r)} Z`
  );
};

export const render = (fragment: Fragment, over: Partial<Options> = {}): string => {
  const o = { ...defaults, ...over };
  const draw = new Draw();
  const byId = new Map(fragment.people.map((p) => [p.id, p]));
  const bondById = new Map(fragment.bonds.map((b) => [b.id, b]));
  const events = fragment.events ?? [];
  const unsureP = new Set(fragment.unsurePeople ?? []);
  const unsureB = new Set(fragment.unsureBonds ?? []);
  const asked = new Set(fragment.ask ?? []);
  const adoptedSet = new Set(fragment.adopted ?? []);
  for (const e of events)
    if (e.kind === Kind.Adopted && e.person !== null) adoptedSet.add(e.person);

  const centre = byId.get(fragment.center);
  if (!centre) throw new Error(`no person ${fragment.center} in the fragment`);

  const eventFor = (kind: string, person: number | null, spouse?: number | null) =>
    events.find(
      (e) =>
        e.kind === kind &&
        (person === null || e.person === person || e.spouse === person) &&
        (spouse === undefined ||
          spouse === null ||
          e.spouse === spouse ||
          e.person === spouse),
    ) ?? null;

  const born = (id: number) => year(eventFor(Kind.Birth, id)?.dateTime);
  const died = (id: number) => eventFor(Kind.Death, id);
  const ageOf = (id: number) => {
    const b = born(id);
    const d = year(died(id)?.dateTime);
    return b !== null && d !== null ? d - b : null;
  };

  const placed: At[] = [];

  const place = (p: FragPerson, x: number, y: number, index = false) => {
    const at: At = { p, x, y, index, faint: unsureP.has(p.id) };
    placed.push(at);
    return at;
  };

  const bondOf = (id: number) => bondById.get(id) ?? null;

  const partnerIn = (bond: FragBond, self: number) =>
    (bond.person_a === self ? bond.person_b : bond.person_a) ?? null;

  const ordered = (bond: FragBond): [FragPerson | null, FragPerson | null] => {
    const a = bond.person_a !== null ? (byId.get(bond.person_a) ?? null) : null;
    const b = bond.person_b !== null ? (byId.get(bond.person_b) ?? null) : null;
    if (!a || !b) return [a, b];
    if (o.side === Side.RecordOrder) return [a, b];
    if (o.side === Side.MaleLeft) {
      if (sexOf(a) === Sex.Male && sexOf(b) !== Sex.Male) return [a, b];
      if (sexOf(b) === Sex.Male && sexOf(a) !== Sex.Male) return [b, a];
    }
    const ya = born(a.id);
    const yb = born(b.id);
    if (ya !== null && yb !== null && yb < ya) return [b, a];
    return [a, b];
  };

  const kidsOf = (bondId: number) =>
    fragment.people
      .filter((p) => p.parents === bondId && p.id !== fragment.center)
      .sort((a, b) => {
        const ya = born(a.id);
        const yb = born(b.id);
        if (ya === null || yb === null) return 0;
        return ya - yb;
      });

  const bondStroke = (bond: FragBond) => {
    const married = bond.married === true || !!eventFor(Kind.Married, bond.person_a, bond.person_b);
    const divorced = !!eventFor(Kind.Divorced, bond.person_a, bond.person_b);
    return { dashed: !married && !divorced, faint: unsureB.has(bond.id) };
  };

  /** The squared U, its crossbar level, and the slashes that say it ended. */
  const drawBond = (
    bond: FragBond | null,
    left: { x: number; y: number } | null,
    right: { x: number; y: number } | null,
    faint: boolean,
    depth: number,
  ): { bar: number; x1: number; x2: number } => {
    const ends = [left, right].filter((e): e is { x: number; y: number } => !!e);
    const bar = Math.max(...ends.map((e) => e.y + 0.5)) + depth;
    const dashed = bond ? bondStroke(bond).dashed : true;
    if (left && right) {
      draw.line(
        `M ${num(left.x)} ${num(left.y + 0.5)} V ${num(bar)} H ${num(right.x)} V ${num(right.y + 0.5)}`,
        { faint, dashed },
      );
    } else if (ends.length === 1) {
      const one = ends[0];
      const to = one.x + (left ? 1 : -1);
      draw.line(`M ${num(one.x)} ${num(one.y + 0.5)} V ${num(bar)} H ${num(to)}`, {
        faint,
        dashed,
      });
      return { bar, x1: Math.min(one.x, to), x2: Math.max(one.x, to) };
    }
    const xs = ends.map((e) => e.x);
    return { bar, x1: Math.min(...xs), x2: Math.max(...xs) };
  };

  const drawSlashes = (bond: FragBond, bar: number, x1: number, x2: number) => {
    const sep = eventFor(Kind.Separated, bond.person_a, bond.person_b);
    const div = eventFor(Kind.Divorced, bond.person_a, bond.person_b);
    const count = div ? 2 : sep ? 1 : 0;
    if (!count) return;
    const mid = (x1 + x2) / 2 + SLASH_RIGHT;
    const lean = o.slash === Slash.Diagonal ? SLASH_LEAN : 0;
    for (let i = 0; i < count; i += 1) {
      const x = mid + i * SLASH_STEP;
      draw.line(
        `M ${num(x)} ${num(bar + SLASH_DROP)} L ${num(x + lean)} ${num(bar + SLASH_DROP - SLASH_RISE)}`,
      );
    }
  };

  const drawChildLine = (
    child: At,
    bar: number,
    x1: number,
    x2: number,
    dashed: boolean,
    faint: boolean,
  ) => {
    const top = child.y - 0.5;
    const x = Math.min(Math.max(child.x, x1), x2);
    draw.line(
      `M ${num(child.x)} ${num(top)} L ${num(x)} ${num(bar)}`,
      { flat: true, dashed, faint },
    );
  };

  const drawPerson = (at: At) => {
    const sex = sexOf(at.p);
    const colour = at.faint ? "faint" : "ink";
    const paint = (half: number) =>
      draw.add(
        `<path class="frag-shape" d="${shapePath(sex, at.x, at.y, half, o.apex)}" ` +
          `fill="none" stroke="var(--${colour})" stroke-width="${num(STROKE)}" ` +
          `stroke-linejoin="round" stroke-linecap="round" />`,
      );
    paint(0.5);
    if (at.index) paint(0.5 + INDEX_GROW);
    draw.seen(at.x - 0.75, at.y - 0.75);
    draw.seen(at.x + 0.75, at.y + 0.75);

    if (sex === Sex.Unknown && o.unknownMark === UnknownMark.Question)
      draw.text("?", at.x, at.y + AGE_SIZE * 0.36, AGE_SIZE, colour, "frag-age");

    const age = ageOf(at.p.id);
    const dead = !!died(at.p.id);
    if (age !== null && sex !== Sex.Miscarriage && sex !== Sex.Abortion)
      draw.text(String(age), at.x, at.y + AGE_SIZE * 0.36, AGE_SIZE, colour, "frag-age");
    if (dead) {
      if (age !== null) {
        for (const [sx, sy] of [
          [-1, -1],
          [1, -1],
          [-1, 1],
          [1, 1],
        ]) {
          const cx = at.x + sx * 0.5;
          const cy = at.y + sy * 0.5;
          draw.line(
            `M ${num(cx)} ${num(cy)} L ${num(cx - sx * TICK)} ${num(cy - sy * TICK)}`,
          );
        }
      } else {
        draw.line(
          `M ${num(at.x - 0.5)} ${num(at.y - 0.5)} L ${num(at.x + 0.5)} ${num(at.y + 0.5)}`,
        );
        draw.line(
          `M ${num(at.x + 0.5)} ${num(at.y - 0.5)} L ${num(at.x - 0.5)} ${num(at.y + 0.5)}`,
        );
      }
    }

    if (asked.has(at.p.id))
      draw.text("?", at.x + 0.62, at.y - 0.46, AGE_SIZE, "ask", "frag-ask");

    const unnamedShown = !at.p.name && o.unnamed === Unnamed.Dashes;
    if (at.p.name || unnamedShown) {
      const fitted = fitName(
        at.p.name ?? "—",
        o.nameFit,
        o.siblingGap,
        NAME_SIZE,
      );
      fitted.lines.forEach((line, i) => {
        draw.text(
          line,
          at.x,
          at.y + NAME_DROP + i * fitted.size * 1.15,
          fitted.size,
          colour,
          "frag-name",
        );
        draw.seen(at.x, at.y + NAME_DROP + i * fitted.size * 1.15 + 0.2);
      });
    }
    if (!at.p.name && o.unnamed === Unnamed.Asked)
      draw.text("?", at.x, at.y + NAME_DROP, NAME_SIZE, "ask", "frag-ask");
  };

  // --- the parents' bond, above -------------------------------------------
  const centreAt = place(centre, 0, 0, true);
  const parentBond = centre.parents !== null ? bondOf(centre.parents) : null;
  if (parentBond) {
    const [l, r] = ordered(parentBond);
    const y = -o.generationGap;
    const half = o.partnerGap / 2;
    const faint = unsureB.has(parentBond.id);
    const lAt = l ? place(l, -half, y) : null;
    const rAt = r ? place(r, half, y) : null;
    let geom;
    if (lAt && rAt) {
      geom = drawBond(parentBond, lAt, rAt, faint, DEPTH);
    } else if (o.single === Single.Ghost) {
      const only = lAt ?? rAt!;
      const ghost: FragPerson = { id: -1, name: null, gender: null, parents: null };
      const other = place(ghost, only === lAt ? half : -half, y);
      other.faint = true;
      geom = drawBond(parentBond, lAt ?? other, rAt ?? other, faint, DEPTH);
    } else if (o.single === Single.NoStub) {
      const only = (lAt ?? rAt)!;
      geom = { bar: only.y + 0.5 + DEPTH, x1: only.x, x2: only.x };
      draw.line(`M ${num(only.x)} ${num(only.y + 0.5)} V ${num(geom.bar)}`, { faint });
    } else {
      geom = drawBond(parentBond, lAt, rAt, faint, DEPTH);
    }
    drawSlashes(parentBond, geom.bar, geom.x1, geom.x2);
    drawChildLine(centreAt, geom.bar, geom.x1, geom.x2, adoptedSet.has(centre.id) && o.adoptLine === AdoptLine.Dashed, faint);
  }

  // --- the centre person's own bonds, beside -------------------------------
  const own = fragment.bonds.filter(
    (b) => b.person_a === fragment.center || b.person_b === fragment.center,
  );
  const startOf = (bond: FragBond) =>
    year(
      (eventFor(Kind.Married, bond.person_a, bond.person_b) ??
        eventFor(Kind.Bonded, bond.person_a, bond.person_b))?.dateTime ?? null,
    ) ?? 0;
  own.sort((a, b) =>
    o.bondOrder === BondOrder.EarliestNearest
      ? startOf(a) - startOf(b)
      : startOf(b) - startOf(a),
  );

  let cursor = -Infinity;
  own.forEach((bond, i) => {
    const partnerId = partnerIn(bond, fragment.center);
    const partner = partnerId !== null ? (byId.get(partnerId) ?? null) : null;
    const x = (i + 1) * o.partnerGap;
    const faint = unsureB.has(bond.id);
    const depth = DEPTH + i * 0.5;
    let geom;
    if (partner) {
      const pAt = place(partner, x, 0);
      if (!partner.name && o.unnamed !== Unnamed.Dashes) pAt.faint = true;
      geom = drawBond(bond, centreAt, pAt, faint, depth);
    } else if (o.single === Single.Ghost) {
      const ghost: FragPerson = { id: -2 - i, name: null, gender: null, parents: null };
      const gAt = place(ghost, x, 0);
      gAt.faint = true;
      geom = drawBond(bond, centreAt, gAt, faint, depth);
    } else if (o.single === Single.NoStub) {
      geom = { bar: 0.5 + depth, x1: 0, x2: 0 };
      draw.line(`M 0 ${num(0.5)} V ${num(geom.bar)}`, { faint });
    } else {
      geom = drawBond(bond, centreAt, null, faint, depth);
    }
    drawSlashes(bond, geom.bar, geom.x1, geom.x2);

    const kids = kidsOf(bond.id);
    const mid = (geom.x1 + geom.x2) / 2;
    const kidAt = new Map<number, At>();
    // Each bond's children keep their own block on the row: centred under their
    // own bar, pushed right when the bond before them already took that room.
    const start = Math.max(
      mid - ((kids.length - 1) / 2) * o.siblingGap,
      cursor + o.siblingGap,
    );
    kids.forEach((kid, k) => {
      const kx = start + k * o.siblingGap;
      kidAt.set(kid.id, place(kid, kx, o.generationGap));
      cursor = kx;
    });

    const groups = (fragment.twins ?? []).map((ids) =>
      ids.filter((id) => kidAt.has(id)),
    );
    const twinned = new Set(groups.flat());

    for (const kid of kids) {
      if (twinned.has(kid.id)) continue;
      const at = kidAt.get(kid.id)!;
      drawChildLine(
        at,
        geom.bar,
        geom.x1,
        geom.x2,
        adoptedSet.has(kid.id) && o.adoptLine === AdoptLine.Dashed,
        faint,
      );
    }

    for (const ids of groups) {
      if (ids.length < 2) continue;
      const ats = ids.map((id) => kidAt.get(id)!);
      const top = Math.min(...ats.map((a) => a.y - 0.5));
      const shared =
        o.twinBar === TwinBar.Fixed ? top - TWIN_RISE : (top + geom.bar) / 2;
      const xs = ats.map((a) => a.x);
      draw.line(`M ${num(Math.min(...xs))} ${num(shared)} H ${num(Math.max(...xs))}`, {
        flat: true,
        faint,
      });
      for (const a of ats)
        draw.line(`M ${num(a.x)} ${num(a.y - 0.5)} V ${num(shared)}`, {
          flat: true,
          faint,
          dashed: adoptedSet.has(a.p.id) && o.adoptLine === AdoptLine.Dashed,
        });
      const centreX = (Math.min(...xs) + Math.max(...xs)) / 2;
      const riseX = Math.min(Math.max(centreX, geom.x1), geom.x2);
      draw.line(`M ${num(centreX)} ${num(shared)} L ${num(riseX)} ${num(geom.bar)}`, {
        flat: true,
        faint,
      });
    }
  });

  // --- a child whose parents' bond is not in the record --------------------
  const loose = (fragment.loose ?? [])
    .map((id) => byId.get(id))
    .filter((p): p is FragPerson => !!p);
  if (loose.length) {
    const startX = Math.max(
      (own.length + 1) * o.partnerGap,
      cursor + o.siblingGap * 1.5,
    );
    loose.forEach((p, i) => {
      const at = place(p, startX + i * o.siblingGap, o.generationGap);
      at.faint = false;
      const bar = 0.5 + DEPTH;
      if (o.loose === Loose.Stub || o.loose === Loose.GhostBond) {
        const half = o.loose === Loose.GhostBond ? o.partnerGap / 2 : 0.5;
        draw.line(`M ${num(at.x - half)} ${num(bar)} H ${num(at.x + half)}`, {
          faint: true,
          dashed: true,
        });
        if (o.loose === Loose.GhostBond) {
          for (const gx of [at.x - half, at.x + half]) {
            const ghost = place(
              { id: -50 - i - gx, name: null, gender: null, parents: null },
              gx,
              0,
            );
            ghost.faint = true;
            draw.line(`M ${num(gx)} ${num(0.5)} V ${num(bar)}`, {
              faint: true,
              dashed: true,
            });
          }
        }
        draw.line(`M ${num(at.x)} ${num(at.y - 0.5)} V ${num(bar)}`, {
          flat: true,
          faint: true,
        });
        draw.text("?", at.x + 0.62, bar - 0.12, AGE_SIZE, "ask", "frag-ask");
      } else {
        draw.line(`M ${num(at.x)} ${num(at.y - 0.5)} V ${num(bar + 0.3)}`, {
          flat: true,
          faint: true,
          dashed: true,
        });
        draw.text("?", at.x, bar + 0.1, AGE_SIZE, "ask", "frag-ask");
      }
    });
  }

  for (const at of placed) drawPerson(at);

  const pad = 0.35;
  const x = draw.min.x - pad;
  const y = draw.min.y - pad;
  const w = draw.max.x - draw.min.x + pad * 2;
  const h = draw.max.y - draw.min.y + pad * 2;
  return (
    `<svg class="fragment" viewBox="${num(x)} ${num(y)} ${num(w)} ${num(h)}" ` +
    `width="${num(w * o.u)}" height="${num(h * o.u)}" ` +
    `role="img" style="background:var(--panel);font-family:var(--sans)">` +
    draw.parts.join("") +
    `</svg>`
  );
};
