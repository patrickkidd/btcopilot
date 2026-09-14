/** The family fragment: one person in the middle, their parents' bond above,
 * their own bond or bonds beside, the children under each bond. Fixed template
 * positions, no search, no crossing avoidance. Every measure is a fraction of
 * `u`, the person box, exactly as doc/chat-first/FRAGMENT_CONVENTIONS.md sets
 * it out. Every rule the gallery put to Patrick is ruled (R-0325); there are no
 * drawing options left, only the size the picture is drawn at. */

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
  /** Children whose parents' bond is not in the record; they stand alone. */
  loose?: number[];
  /** People the record has adopted into a bond rather than born into it, when
   * no adoption event carries it. */
  adopted?: number[];
  /** What the fragment asks about, by person id: an amber question mark. */
  ask?: number[];
}

export interface Options {
  /** Pixels per person box. */
  u: number;
}

export const defaults: Options = { u: 44 };

const STROKE = 0.03;
const DEPTH = 0.45;
const INDEX_GROW = 0.1;
const SLASH_RIGHT = 0.75;
const SLASH_RISE = 0.4;
const SLASH_DROP = 0.15;
const SLASH_STEP = 0.1;
const TWIN_RISE = 0.34;
const TICK = 0.3;
const NAME_SIZE = 0.25;
const AGE_SIZE = 0.3;
const NAME_DROP = 0.78;
const CHAR = 0.53;
/** Centre to centre, in person boxes. */
const SIBLING_GAP = 2;
const GENERATION_GAP = 2;
const PARTNER_GAP = 2;

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

/** The given name only, on one line, cut with an ellipsis at the box width plus
 * one sibling gap. */
export const fitName = (name: string, size: number): string => {
  const given = [...name.trim().split(/\s+/)[0]];
  const max = Math.max(3, Math.floor(SIBLING_GAP / (size * CHAR)));
  return given.length <= max
    ? given.join("")
    : given.slice(0, max - 1).join("") + "…";
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

const shapePath = (sex: Sex, x: number, y: number, half: number) => {
  if (sex === Sex.Miscarriage || sex === Sex.Abortion) {
    return (
      `M ${num(x)} ${num(y - half)} L ${num(x + half)} ${num(y + half)} ` +
      `L ${num(x - half)} ${num(y + half)} Z`
    );
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

  /** Both sides of a bond are people in the record: a parent or partner nobody
   * named is still extracted as a person with a generic name. A bond with a
   * side missing is a record fault, not something to draw around. */
  const sideOf = (bond: FragBond, which: "person_a" | "person_b") => {
    const id = bond[which];
    const p = id !== null ? byId.get(id) : undefined;
    if (!p) throw new Error(`bond ${bond.id} has no ${which} in the fragment`);
    return p;
  };

  const partnerIn = (bond: FragBond, self: number) =>
    sideOf(bond, bond.person_a === self ? "person_b" : "person_a");

  /** Male on the left, female on the right; with no man, the older person left,
   * then record order. */
  const ordered = (bond: FragBond): [FragPerson, FragPerson] => {
    const a = sideOf(bond, "person_a");
    const b = sideOf(bond, "person_b");
    if (sexOf(a) === Sex.Male && sexOf(b) !== Sex.Male) return [a, b];
    if (sexOf(b) === Sex.Male && sexOf(a) !== Sex.Male) return [b, a];
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

  const bondDashed = (bond: FragBond) => {
    const married =
      bond.married === true || !!eventFor(Kind.Married, bond.person_a, bond.person_b);
    const divorced = !!eventFor(Kind.Divorced, bond.person_a, bond.person_b);
    return !married && !divorced;
  };

  /** The squared U and its crossbar level. */
  const drawBond = (
    bond: FragBond,
    left: { x: number; y: number },
    right: { x: number; y: number },
    faint: boolean,
    depth: number,
  ): { bar: number; x1: number; x2: number } => {
    const bar = Math.max(left.y, right.y) + 0.5 + depth;
    draw.line(
      `M ${num(left.x)} ${num(left.y + 0.5)} V ${num(bar)} H ${num(right.x)} V ${num(right.y + 0.5)}`,
      { faint, dashed: bondDashed(bond) },
    );
    return { bar, x1: Math.min(left.x, right.x), x2: Math.max(left.x, right.x) };
  };

  /** One mark for a separation, two for a divorce, straight up and down. */
  const drawSlashes = (bond: FragBond, bar: number, x1: number, x2: number) => {
    const sep = eventFor(Kind.Separated, bond.person_a, bond.person_b);
    const div = eventFor(Kind.Divorced, bond.person_a, bond.person_b);
    const count = div ? 2 : sep ? 1 : 0;
    const mid = (x1 + x2) / 2 + SLASH_RIGHT;
    for (let i = 0; i < count; i += 1) {
      const x = mid + i * SLASH_STEP;
      draw.line(
        `M ${num(x)} ${num(bar + SLASH_DROP)} L ${num(x)} ${num(bar + SLASH_DROP - SLASH_RISE)}`,
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
    draw.line(`M ${num(child.x)} ${num(top)} L ${num(x)} ${num(bar)}`, {
      flat: true,
      dashed,
      faint,
    });
  };

  const drawPerson = (at: At) => {
    const sex = sexOf(at.p);
    const colour = at.faint ? "faint" : "ink";
    const paint = (half: number) =>
      draw.add(
        `<path class="frag-shape" d="${shapePath(sex, at.x, at.y, half)}" ` +
          `fill="none" stroke="var(--${colour})" stroke-width="${num(STROKE)}" ` +
          `stroke-linejoin="round" stroke-linecap="round" />`,
      );
    paint(0.5);
    if (at.index) paint(0.5 + INDEX_GROW);
    draw.seen(at.x - 0.75, at.y - 0.75);
    draw.seen(at.x + 0.75, at.y + 0.75);

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

    if (at.p.name) {
      draw.text(
        fitName(at.p.name, NAME_SIZE),
        at.x,
        at.y + NAME_DROP,
        NAME_SIZE,
        colour,
        "frag-name",
      );
      draw.seen(at.x, at.y + NAME_DROP + 0.2);
    }
  };

  // --- the parents' bond, above -------------------------------------------
  const centreAt = place(centre, 0, 0, true);
  const parentBond = centre.parents !== null ? (bondById.get(centre.parents) ?? null) : null;
  if (parentBond) {
    const [l, r] = ordered(parentBond);
    const y = -GENERATION_GAP;
    const half = PARTNER_GAP / 2;
    const faint = unsureB.has(parentBond.id);
    const geom = drawBond(
      parentBond,
      place(l, -half, y),
      place(r, half, y),
      faint,
      DEPTH,
    );
    drawSlashes(parentBond, geom.bar, geom.x1, geom.x2);
    drawChildLine(centreAt, geom.bar, geom.x1, geom.x2, adoptedSet.has(centre.id), faint);
  }

  // --- the centre person's own bonds, beside -------------------------------
  // Earliest bond nearest the middle person, later ones further right; each U
  // is deeper than the one before it, so the bars overlap horizontally and one
  // reaches further right than the other.
  const own = fragment.bonds.filter(
    (b) => b.person_a === fragment.center || b.person_b === fragment.center,
  );
  const startOf = (bond: FragBond) =>
    year(
      (eventFor(Kind.Married, bond.person_a, bond.person_b) ??
        eventFor(Kind.Bonded, bond.person_a, bond.person_b))?.dateTime ?? null,
    );
  own.sort((a, b) => {
    const ya = startOf(a);
    const yb = startOf(b);
    return ya === null || yb === null ? 0 : ya - yb;
  });

  let cursor = -Infinity;
  own.forEach((bond, i) => {
    const partner = partnerIn(bond, fragment.center);
    const faint = unsureB.has(bond.id);
    const geom = drawBond(
      bond,
      centreAt,
      place(partner, (i + 1) * PARTNER_GAP, 0),
      faint,
      DEPTH + i * 0.5,
    );
    drawSlashes(bond, geom.bar, geom.x1, geom.x2);

    const kids = kidsOf(bond.id);
    const mid = (geom.x1 + geom.x2) / 2;
    const kidAt = new Map<number, At>();
    // Each bond's children keep their own block on the row: centred under their
    // own bar, pushed right when the bond before them already took that room.
    const start = Math.max(
      mid - ((kids.length - 1) / 2) * SIBLING_GAP,
      cursor + SIBLING_GAP,
    );
    kids.forEach((kid, k) => {
      const kx = start + k * SIBLING_GAP;
      kidAt.set(kid.id, place(kid, kx, GENERATION_GAP));
      cursor = kx;
    });

    const groups = (fragment.twins ?? []).map((ids) =>
      ids.filter((id) => kidAt.has(id)),
    );
    const twinned = new Set(groups.flat());

    for (const kid of kids) {
      if (twinned.has(kid.id)) continue;
      drawChildLine(
        kidAt.get(kid.id)!,
        geom.bar,
        geom.x1,
        geom.x2,
        adoptedSet.has(kid.id),
        faint,
      );
    }

    for (const ids of groups) {
      if (ids.length < 2) continue;
      const ats = ids.map((id) => kidAt.get(id)!);
      const top = Math.min(...ats.map((a) => a.y - 0.5));
      const shared = top - TWIN_RISE;
      const xs = ats.map((a) => a.x);
      draw.line(`M ${num(Math.min(...xs))} ${num(shared)} H ${num(Math.max(...xs))}`, {
        flat: true,
        faint,
      });
      for (const a of ats)
        draw.line(`M ${num(a.x)} ${num(a.y - 0.5)} V ${num(shared)}`, {
          flat: true,
          faint,
          dashed: adoptedSet.has(a.p.id),
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
  // They stand alone on the children's row: no bar, no riser, nothing invented.
  const loose = (fragment.loose ?? [])
    .map((id) => byId.get(id))
    .filter((p): p is FragPerson => !!p);
  const looseStart = Math.max((own.length + 1) * PARTNER_GAP, cursor + SIBLING_GAP * 1.5);
  loose.forEach((p, i) => {
    place(p, looseStart + i * SIBLING_GAP, GENERATION_GAP);
  });

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
