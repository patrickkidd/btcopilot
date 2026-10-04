import { esc } from "./dom";

/** The ratified move language (OWNER_RULINGS 2026-09-01, batches 1-3, and the
 * 2026-09-02 rulings), drawn on the people the play-by-play puts on stage.
 *
 * Every stroke width, dash array, duration, easing and key-time here is copied
 * from the ratified demos in `design/move-language.html`. Only the geometry
 * that depends on where two people happen to stand is computed: each pair move
 * is drawn in a local frame whose x axis runs from the mover to whoever the
 * move reaches, so the ratified drawing keeps its proportions at any angle.
 *
 * One green for every move mark; amber is never used here, because amber only
 * ever means the record asking. */

export enum Move {
  Toward = "toward",
  Away = "away",
  Distance = "distance",
  Cutoff = "cutoff",
  Conflict = "conflict",
  DefinedSelf = "defined-self",
  Inside = "inside",
  Outside = "outside",
  Fusion = "fusion",
  Overfunctioning = "overfunctioning",
  Underfunctioning = "underfunctioning",
  Projection = "projection",
}

export enum Shift {
  Up = "up",
  Down = "down",
  Same = "same",
}

export enum Sex {
  Female = "female",
}

export interface Figure {
  id: number;
  name: string;
  x: number;
  y: number;
  /** Family-diagram shapes, by sex: a circle for a woman, a square otherwise. */
  gender?: string | null;
  /** Half-size: the circle's radius, or half the square's side. */
  r?: number;
  /** Side marks go left of people standing on the right of the board, so they
   * never run off its edge. */
  mirror?: boolean;
  /** The board they stand on, so a walk stops at its edge. */
  stage?: { w: number; h: number };
  /** The board writes names above its people; the stage writes them below. */
  above?: boolean;
  /** How tall a wall stands, and the conflict burst with it: the ratified 68,
   * unless the drawing holds all its marks to one size of its own, as the
   * play-by-play does. */
  mark?: number;
  /** The drawing's people never move, as in the play-by-play (R-0546), so a
   * move's drawing in is carried by its marks alone. */
  still?: boolean;
}

/** The play-by-play stage, where pane A is the fidelity standard. */
export const R = 17;
/** The moves board, as the ratified board drawing sizes people. */
export const BOARD_R = 13;

/** The one set of speeds every mark moves at (Patrick, 2026-10-03), in
 * seconds: an arrow's dashes travelling, a field's rings spreading, a new mark
 * popping in, and a mark growing or shrinking. theme.css carries the same
 * numbers as --speed-* for the marks drawn by CSS; a test holds them equal. */
export const SPEED = { arrow: 1, ring: 1.65, pop: 0.2, grow: 1.4 };
const s_ = (v: number) => `${v}s`;

/** How far anxiety's spikes reach past a figure's edge: their gap and the
 * longest of them. */
export const SPIKES = 2 + 12;
/** The flank arrow beside a person: how far past their edge it stands, how
 * wide its head spreads, and how far it reaches above and below their middle. */
export const FLANK = { at: 13, wing: 7, half: 11 };
/** Where a wall stands, as a share of the way from the mover to the other:
 * further in front of the actor, as ratified. */
export const WALL = 0.4375;

/** The ratified story loop. Heavier marks run a multiple of it. */
export const LOOP = 8;

/** The ratified demos are drawn in a 230x130 box. What was ratified is the
 * drawing's proportions, not its arithmetic, so a ratified length scales to the
 * board it lands on (UI_SPEC resolution 42). Marks that carry no proportion —
 * stroke widths, dash arrays, spike lengths — keep their ratified numbers. */
export const DEMO = { w: 230, h: 130 };
/** How far a person's emotional field reaches on the ratified demo stage. */
export const FIELD = 170;
const tall = (f: Figure) => (f.stage ? f.stage.h / DEMO.h : 1);
const wide = (f: Figure) => (f.stage ? f.stage.w / DEMO.w : 1);

const rad = (f: Figure) => f.r ?? R;
/** The square is 24 wide against the circle's r=13, per the ratified shapes. */
const half = (f: Figure) => rad(f) * (12 / 13);

let seq = 0;
const uid = (prefix: string) => `${prefix}${++seq}`;

const EASE = ".42 0 .58 1";
const splines = (n: number) => Array.from({ length: n }, () => EASE).join(";");

const n1 = (v: number) => v.toFixed(1);

interface Frame {
  /** Distance from the mover to whoever the move reaches. */
  length: number;
  open: string;
  close: string;
}

/** A local frame with the mover at the origin and the one they reach straight
 * out along +x, so every ratified drawing can be copied as it was drawn. */
function frame(from: Figure, to: Figure): Frame {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy) || 1;
  const deg = (Math.atan2(dy, dx) * 180) / Math.PI;
  return {
    length,
    open: `<g class="mv" transform="translate(${n1(from.x)} ${n1(from.y)}) rotate(${deg.toFixed(2)})">`,
    close: `</g>`,
  };
}

const unit = (a: Figure, b: Figure) => {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = Math.hypot(dx, dy) || 1;
  return { x: dx / length, y: dy / length, length };
};

/** A person's own motion, on the ratified key times of its move. `at` is the
 * fraction of the whole displacement held at each key time. */
export interface Walk {
  values: string;
  keyTimes: string;
  dur: string;
}

function walk(
  dx: number,
  dy: number,
  at: number[],
  keyTimes: string,
  dur: string,
): Walk {
  return {
    values: at.map((k) => `${n1(dx * k)} ${n1(dy * k)}`).join(";"),
    keyTimes,
    dur,
  };
}

/** A walk keeps its ratified length, scaled to the board. Where the mover has
 * no room for it, the layout gives and the walk does not: the mover starts
 * further in, so the same move is the same drawing wherever the person happens
 * to stand (UI_SPEC resolution 43). */
function makeRoom(who: Figure, dx: number, dy: number): [number, number] {
  const box = who.stage;
  if (!box) return [0, 0];
  const pad = rad(who) + 10;
  const over = (from: number, delta: number, limit: number) => {
    const end = from + delta;
    if (end < pad) return pad - end;
    if (end > limit - pad) return limit - pad - end;
    return 0;
  };
  return [over(who.x, dx, box.w), over(who.y, dy, box.h)];
}

/** The same figure, stood far enough in that its whole walk fits. */
function stoodBack(who: Figure, dx: number, dy: number): [Figure, [number, number]] {
  const [sx, sy] = makeRoom(who, dx, dy);
  if (!sx && !sy) return [who, [0, 0]];
  return [{ ...who, x: who.x + sx, y: who.y + sy }, [sx, sy]];
}

/** An attribute animated across the story loop, on ratified key times. */
function animate(
  name: string,
  values: string,
  keyTimes: string,
  dur: string,
  begin = "0s",
): string {
  return (
    `<animate attributeName="${name}" values="${values}" keyTimes="${keyTimes}" ` +
    `dur="${dur}" begin="${begin}" repeatCount="indefinite" fill="freeze"/>`
  );
}

/* -------------------------------------------------------------------------
 * people
 * ---------------------------------------------------------------------- */

/** A person: the family-diagram shape that never leaves them, their initial,
 * and their name under it. The sharp outline is always drawn — the actor never
 * disappears. */
export function figure(
  person: Figure,
  classes = "",
  ghost: "" | "out" | "in" | "solo" = "",
  step?: Walk,
): string {
  const initial = person.name.trim().slice(0, 1).toUpperCase() || "?";
  const r = rad(person);
  const s = half(person);
  const female = (person.gender ?? "").toLowerCase() === Sex.Female;
  const shape = (klass: string, extra = "") =>
    female
      ? `<circle class="${klass}" cx="${n1(person.x)}" cy="${n1(person.y)}" r="${r}"${extra}/>`
      : `<rect class="${klass}" x="${n1(person.x - s)}" y="${n1(person.y - s)}" ` +
        `width="${n1(s * 2)}" height="${n1(s * 2)}"${extra}/>`;
  const blur = ghost ? uid("gb") : "";
  const moved = step
    ? `<animateTransform attributeName="transform" type="translate" ` +
      `values="${step.values}" keyTimes="${step.keyTimes}" dur="${step.dur}" ` +
      `calcMode="spline" keySplines="${splines(step.keyTimes.split(";").length - 1)}" ` +
      `repeatCount="indefinite" fill="freeze"/>`
    : "";
  return (
    `<g class="node" data-person="${person.id}">${moved}` +
    (ghost
      ? `<defs><filter id="${blur}" x="-60%" y="-60%" width="220%" height="220%">` +
        `<feGaussianBlur stdDeviation="1.2"/></filter></defs>` +
        `<g class="ghost g-${ghost}" filter="url(#${blur})">${shape("gh")}</g>`
      : "") +
    `<g class="body ${classes}">` +
    shape("disc") +
    `<text class="ini" x="${n1(person.x)}" y="${n1(person.y + 4)}" text-anchor="middle">${esc(initial)}</text>` +
    `</g>` +
    // clear of the outermost field ring, so a name is never drawn through one
    `<text class="nm${classes.includes("mover") ? " on" : ""}" x="${n1(person.x)}" ` +
    `y="${n1(person.above ? person.y - r - 7 : person.y + r + 32)}" text-anchor="middle">` +
    `${esc(person.name)}</text>` +
    `</g>`
  );
}

/* -------------------------------------------------------------------------
 * the marks
 * ---------------------------------------------------------------------- */

/** A person's emotional field: three rings that never fade or bounce, running
 * out to 170 over 1.65s, each starting a beat after the last. */
function rings(
  cx: number,
  cy: number,
  klass: string,
  clip = "",
  width = 2.4,
  to = FIELD,
  dur = s_(SPEED.ring),
  fade = ".75;.45;0",
): string {
  to = Math.round(to);
  return [0, 0.55, 1.1]
    .map(
      (begin) =>
        `<circle class="fld ${klass}" cx="${n1(cx)}" cy="${n1(cy)}" r="24" ` +
        `stroke-width="${width}" opacity="0"${clip}>` +
        `<animate attributeName="r" values="18;${to}" dur="${dur}" ` +
        `begin="${begin}s" repeatCount="indefinite"/>` +
        `<animate attributeName="opacity" values="${fade}" keyTimes="0;.75;1" ` +
        `dur="${dur}" begin="${begin}s" repeatCount="indefinite"/>` +
        `</circle>`,
    )
    .join("");
}

/** Withdrawal: one push raises a wall between the two. The other's field wraps
 * the wall's ends but never enters the wedge of shadow behind it, and a dashed
 * trace says whose wall it is. Cutoff is the same drawing with a line struck
 * through the wall. */
function wall(frm: Frame, mover: Figure, struck: boolean): string {
  const L = frm.length;
  const wx = L * WALL;
  const arm = (mover.mark ?? 68) / 2;
  const shadow = uid("csh");
  // the wedge behind the wall widens as it runs back, so the rings wrap the
  // wall's ends instead of stopping at a straight line
  const back = -L;
  const spread = arm + 0.419 * (wx - back);
  const strike = struck
    ? `<line class="mv-strike postA" x1="${n1(wx - arm * (13 / 34))}" y1="${n1(arm * (22 / 34))}" ` +
      `x2="${n1(wx + arm * (13 / 34))}" y2="${n1(-arm * (22 / 34))}"/>`
    : "";
  return (
    `<defs><clipPath id="${shadow}"><path clip-rule="evenodd" ` +
    `d="M${n1(back)} ${n1(-spread - 40)} H${n1(L * 2)} V${n1(spread + 40)} H${n1(back)} Z ` +
    `M${n1(wx)} ${-arm} L${n1(wx)} ${arm} L${n1(back)} ${n1(spread)} L${n1(back)} ${n1(-spread)} Z"/>` +
    `</clipPath></defs>` +
    rings(L, 0, "preA", "", 2.4, FIELD * tall(mover)) +
    rings(L, 0, "postA", ` clip-path="url(#${shadow})"`, 2.4, FIELD * tall(mover)) +
    `<line class="mv-trace" x1="${n1(rad(mover) + 2)}" y1="0" x2="${n1(wx - 3)}" y2="0" ` +
    // where the people stay put the wall's loop is 5s and it lands at 28%
    `opacity="0">${mover.still ? animate("opacity", "0;0;.55;.55", "0;.28;.32;1", "5s") : animate("opacity", "0;0;.55;.55", "0;.4;.46;1", "8s")}</line>` +
    strike +
    `<line class="mv-wall" x1="${n1(wx)}" y1="${-arm}" x2="${n1(wx)}" y2="${arm}"/>`
  );
}

/** Conflict: sparks fly between two people who are both vibrating. One zigzag
 * along the line, and a radial burst of high-frequency static at its middle. */
function sparks(frm: Frame, mover: Figure, other: Figure): string {
  const L = frm.length;
  const x0 = rad(mover) + 11;
  const x1 = L - rad(other) - 11;
  const points = Array.from({ length: 8 }, (_, i) => {
    const x = x0 + ((x1 - x0) * i) / 7;
    const y = i === 0 || i === 7 ? 0 : i % 2 ? -7 : 7;
    return `${n1(x)},${y}`;
  }).join(" ");
  const mid = (x0 + x1) / 2;
  // the burst keeps its ratified proportion to a wall, at whatever size the drawing holds walls to
  const k = (mover.mark ?? 68) / 68;
  const burst = [
    [0, -17, 0, -29],
    [0, 17, 0, 29],
    [-14, -12, -23, -20],
    [14, -12, 23, -20],
    [-14, 12, -23, 20],
    [14, 12, 23, 20],
  ]
    .map(
      ([ax, ay, bx, by]) =>
        `<line class="mv-burst" x1="${n1(mid + ax * k)}" y1="${n1(ay * k)}" x2="${n1(mid + bx * k)}" y2="${n1(by * k)}"/>`,
    )
    .join("");
  return (
    `<polyline class="mv-spark" points="${points}"/>` +
    `<g class="mv-sparks" style="transform-origin:${n1(mid)}px 0px">${burst}</g>`
  );
}

/** An arrow whose tail travels with the mover: toward, it shrinks into the
 * landing; away, it leads the way out and is gone once they have gone. */
function arrow(
  frm: Frame,
  mover: Figure,
  other: Figure,
  away: boolean,
  travel = 68,
): string {
  const L = frm.length;
  const head = 12;
  const wing = 7;
  if (!away) {
    const tip = L - rad(other) - 4;
    const stem = tip - head;
    return (
      `<g class="tarrow">` +
      `<line class="mv-arrow" x1="${n1(rad(mover) + 3)}" y1="0" x2="${n1(stem)}" y2="0">` +
      animate("x1", `${n1(rad(mover) + 3)};${n1(rad(mover) + 3)};${n1(tip)};${n1(tip)}`, "0;.06;.5;1", "8s") +
      `</line>` +
      `<polygon class="tipfill" points="${n1(tip)},0 ${n1(stem)},${-wing} ${n1(stem)},${wing}"/>` +
      `</g>`
    );
  }
  const start = -(rad(mover) + 2);
  const tail = Math.max(16, travel * (44 / 68));
  const end = start - travel;
  const lead = travel * (38 / 68);
  return (
    `<g class="tarrow">` +
    `<line class="mv-arrow back" x1="${n1(start)}" y1="0" x2="${n1(start - tail)}" y2="0">` +
    animate("x1", `${n1(start)};${n1(start)};${n1(end)};${n1(end)}`, "0;.06;.5;1", "8s") +
    animate("x2", `${n1(start - tail)};${n1(start - tail)};${n1(end - tail)};${n1(end - tail)}`, "0;.06;.5;1", "8s") +
    `</line>` +
    `<polygon class="tipfill" points="${n1(start - tail - head)},0 ${n1(start - tail)},${-wing} ${n1(start - tail)},${wing}">` +
    `<animateTransform attributeName="transform" type="translate" ` +
    `values="0 0;0 0;${n1(-lead)} 0;${n1(-lead)} 0" keyTimes="0;.06;.5;1" dur="8s" repeatCount="indefinite"/>` +
    `</polygon>` +
    `</g>`
  );
}

/** Anxiety, in the one language it uses everywhere: eight spikes of static
 * around the figure, each flickering to its own beat. */
export function spikes(person: Figure, phase: "out" | "in" | "solo"): string {
  const r = rad(person);
  const flicker = {
    out: [0.44, 0.4, 0.29, 0.39, 0.3, 0.45, 0.27, 0.45],
    in: [0.32, 0.3, 0.54, 0.55, 0.58, 0.51, 0.36, 0.49],
    solo: [0.44, 0.4, 0.29, 0.39, 0.3, 0.45, 0.27, 0.45],
  }[phase];
  const lines = flicker
    .map((dur, i) => {
      const angle = (i / 8) * Math.PI * 2;
      const length = 6 + (i % 3) * 3;
      const ax = Math.cos(angle) * (r + 2);
      const ay = Math.sin(angle) * (r + 2);
      const bx = Math.cos(angle) * (r + 2 + length);
      const by = Math.sin(angle) * (r + 2 + length);
      return (
        `<line class="mv-spike" x1="${n1(ax)}" y1="${n1(ay)}" x2="${n1(bx)}" y2="${n1(by)}" opacity="0">` +
        // where the people stay put, the anxiety a parent passes on is there at
        // full strength from the first frame and never goes out, so the eye
        // sees it before it drains (Patrick, 2026-10-03)
        `<animate attributeName="opacity" values="${person.still && phase === "out" ? "1;.6;1;.6;1" : "0;1;.2;1;0"}" dur="${dur}s" repeatCount="indefinite"/>` +
        `</line>`
      );
    })
    .join("");
  return (
    `<g transform="translate(${n1(person.x)} ${n1(person.y)})">` +
    `<g class="spk s-${phase}">${lines}</g></g>`
  );
}

/** Projection: the parent's agitation drains off along the arrow's own fast
 * dashes and settles onto the child. */
function drainArrow(from: Figure, to: Figure): string {
  const u = unit(from, to);
  const ax = from.x + u.x * (rad(from) + 3);
  const ay = from.y + u.y * (rad(from) + 3);
  const tipX = to.x - u.x * (rad(to) + 4);
  const tipY = to.y - u.y * (rad(to) + 4);
  const stemX = tipX - u.x * 13;
  const stemY = tipY - u.y * 13;
  const nx = -u.y;
  const ny = u.x;
  return (
    `<line class="mv-flow" x1="${n1(ax)}" y1="${n1(ay)}" x2="${n1(stemX)}" y2="${n1(stemY)}"/>` +
    `<polygon class="tipfill" points="${n1(tipX)},${n1(tipY)} ` +
    `${n1(stemX + nx * 7)},${n1(stemY + ny * 7)} ${n1(stemX - nx * 7)},${n1(stemY - ny * 7)}"/>`
  );
}

/** How tall the arrow beside the health cross stands: the cross's own height,
 * ruled 2026-09-08. The ratified sheet drew it at 32, twice the cross, which
 * reads as a mark about the arrow rather than about the person. Every number
 * below is that sheet's, halved; the stroke is the sheet's, unscaled. */
const ARROW = 0.5;

/** The health cross's own width and height. */
export const CROSS = 16;

/** The health cross, and the arrow that says which way it went. Each keeps its
 * own size in a square cell as tall as the cross, the two cells side by side,
 * so the gap between them is even (Patrick, 2026-10-03). */
export function cross(person: Figure, direction: Shift): string {
  const side = person.mirror ? -1 : 1;
  const cx = person.x + side * (rad(person) + 29);
  const cy = person.y - 6;
  const ax = cx + side * CROSS;
  const up = (offset: number) => n1(cy + offset * ARROW);
  const across = (offset: number) => n1(ax + offset * ARROW);
  const worse =
    `<g class="sym-arrow worse">` +
    `<line class="mv-dir" x1="${n1(ax)}" y1="${up(14)}" x2="${n1(ax)}" y2="${up(-12)}"/>` +
    `<polygon class="tipfill" points="${n1(ax)},${up(-18)} ${across(-8)},${up(-8)} ${across(8)},${up(-8)}"/>` +
    `</g>`;
  const better =
    `<g class="sym-arrow better">` +
    `<line class="mv-dir" x1="${n1(ax)}" y1="${up(-12)}" x2="${n1(ax)}" y2="${up(14)}"/>` +
    `<polygon class="tipfill" points="${n1(ax)},${up(20)} ${across(-8)},${up(10)} ${across(8)},${up(10)}"/>` +
    `</g>`;
  const arrow =
    direction === Shift.Up ? worse : direction === Shift.Down ? better : "";
  return (
    `<g class="mv-sym" transform="translate(${n1(cx)} ${n1(cy)})">` +
    `<rect class="tipfill" x="${-CROSS / 2}" y="-3" width="${CROSS}" height="6" rx="1"/>` +
    `<rect class="tipfill" x="-3" y="${-CROSS / 2}" width="6" height="${CROSS}" rx="1"/>` +
    `</g>` +
    arrow
  );
}

/** Fusion, as Bowen drew it: three straight bands holding the pair from the
 * first frame, shrinking as the two are drawn in, and a shared field once they
 * arrive. */
function bands(frm: Frame, a: Figure, b: Figure, closeBy: number): string {
  const L = frm.length;
  const x1 = rad(a) + 1;
  const x2 = L - rad(b) - 1;
  const mid = L / 2;
  // once the two are drawn in they overlap the bands, which then run between
  // their centres rather than between their edges; where the two cannot move,
  // the bands grow out from the middle until they hold both (Patrick, 2026-10-03)
  const [from1, to1] = a.still ? [mid, x1] : [x1, closeBy + rad(a) + 1];
  const [from2, to2] = a.still ? [mid, x2] : [x2, L - closeBy - rad(b) - 1];
  // where the two cannot move, the bands set off at once and take the grow
  // time, the ring spreads once, and the loop then holds for half of what the
  // board's 8s leaves over (Patrick, 2026-10-03)
  const busy = SPEED.grow + SPEED.ring;
  const loop = a.still ? busy + (8 - busy) / 2 : 8;
  const joined = SPEED.grow / loop;
  const times = a.still ? `0;0;${joined};1` : "0;.2;.55;1";
  const ringTimes = `0;${joined - 0.001};${joined};${busy / loop};1`;
  // the shared field: on the board it pulses throughout; where the two cannot
  // move it spreads once, at the ring speed, when the bands have joined them
  const ring = a.still
    ? animate("r", "26;26;26;60;60", ringTimes, s_(loop)) + animate("opacity", "0;0;.5;0;0", ringTimes, s_(loop))
    : `<animate attributeName="r" values="26;60" dur="${s_(SPEED.ring)}" repeatCount="indefinite"/>` +
      `<animate attributeName="opacity" values=".5;0" dur="${s_(SPEED.ring)}" repeatCount="indefinite"/>`;
  return (
    [-6, 0, 6]
      .map(
        (dy) =>
          `<line class="mv-band" x1="${n1(x1)}" y1="${dy}" x2="${n1(x2)}" y2="${dy}">` +
          animate("x1", `${n1(from1)};${n1(from1)};${n1(to1)};${n1(to1)}`, times, s_(loop)) +
          animate("x2", `${n1(from2)};${n1(from2)};${n1(to2)};${n1(to2)}`, times, s_(loop)) +
          `</line>`,
      )
      .join("") +
    `<circle class="mv-shared" cx="${n1(mid)}" cy="0" r="24" opacity="0">${ring}</circle>`
  );
}

/** The flank arrow beside whoever rises or sinks: drawn to the side, about two
 * thirds the size of the person, never as movement. */
function flank(person: Figure, up: boolean): string {
  const side = person.mirror ? -1 : 1;
  const x = person.x + side * (rad(person) + FLANK.at);
  const top = person.y - FLANK.half;
  const bottom = person.y + FLANK.half;
  const tip = up ? top : bottom;
  const back = up ? top + 8 : bottom - 8;
  return (
    `<g class="mv-flank ${up ? "up" : "down"}">` +
    `<line x1="${n1(x)}" y1="${n1(top)}" x2="${n1(x)}" y2="${n1(bottom)}"/>` +
    `<line x1="${n1(x)}" y1="${n1(tip)}" x2="${n1(x - FLANK.wing)}" y2="${n1(back)}"/>` +
    `<line x1="${n1(x)}" y1="${n1(tip)}" x2="${n1(x + FLANK.wing)}" y2="${n1(back)}"/>` +
    `</g>`
  );
}

/** The heat in a triangle: a zigzag, not a plain line, so it reads as tension
 * rather than a bond. */
export function zigzag(from: Figure, to: Figure, klass = "mv-tension"): string {
  const u = unit(from, to);
  const a = rad(from) + 3;
  const b = u.length - rad(to) - 3;
  const nx = -u.y;
  const ny = u.x;
  // the ratified tension zigzag is five points over about 60px; over a longer
  // side it keeps that pitch rather than stretching into a kinked line
  const n = Math.max(5, Math.round((b - a) / 15) | 1);
  const points = Array.from({ length: n }, (_, i) => {
    const along = a + ((b - a) * i) / (n - 1);
    const off = i === 0 || i === n - 1 ? 0 : i % 2 ? 4.5 : -4.5;
    return `${n1(from.x + u.x * along + nx * off)},${n1(from.y + u.y * along + ny * off)}`;
  }).join(" ");
  return `<polyline class="${klass}" points="${points}"/>`;
}

/** The other party's storm, and the calm that only arrives a beat after the
 * actor has held still. */
function storm(other: Figure): string {
  const loud = Math.round(FIELD * tall(other));
  const calm = Math.round(150 * tall(other));
  return (
    `<g class="stormlong">` +
    [0, 0.55]
      .map(
        (begin) =>
          `<circle class="fld" cx="${n1(other.x)}" cy="${n1(other.y)}" r="24" ` +
          `stroke-width="2.6" opacity="0">` +
          `<animate attributeName="r" values="18;${loud}" dur="${s_(SPEED.ring)}" begin="${begin}s" repeatCount="indefinite"/>` +
          `<animate attributeName="opacity" values=".8;.5;0" keyTimes="0;.7;1" dur="${s_(SPEED.ring)}" ` +
          `begin="${begin}s" repeatCount="indefinite"/></circle>`,
      )
      .join("") +
    `</g>` +
    `<g class="stormcalm">` +
    `<circle class="fld" cx="${n1(other.x)}" cy="${n1(other.y)}" r="24" ` +
    `stroke-width="1.6" opacity="0">` +
    `<animate attributeName="r" values="18;${calm}" dur="${s_(SPEED.ring)}" repeatCount="indefinite"/>` +
    `<animate attributeName="opacity" values=".35;.2;0" keyTimes="0;.7;1" dur="${s_(SPEED.ring)}" repeatCount="indefinite"/>` +
    `</circle></g>`
  );
}

/* -------------------------------------------------------------------------
 * one move
 * ---------------------------------------------------------------------- */

export interface Drawn {
  /** Extra classes for the mover's own figure. */
  actor: string;
  /** Extra classes for whoever the move reaches. */
  target: string;
  /** Extra classes for the third person in a triangle. */
  third: string;
  /** Which of the three carries a blurred, shaking ghost-double. */
  ghosts: { actor?: "out" | "in" | "solo"; target?: "out" | "in" | "solo" };
  /** Everything drawn around and between them. */
  marks: string;
  /** Where a person has to stand for their whole walk to fit on the board.
   * The layout gives, never the walk (UI_SPEC resolution 43). */
  place: Record<number, [number, number]>;
  /** How far the move actually moves someone, by person id, on the ratified
   * key times. A move is a move: the person travels. */
  steps: Record<number, Walk>;
}

const NONE: Drawn = {
  actor: "",
  target: "",
  third: "",
  ghosts: {},
  place: {},
  marks: "",
  steps: {},
};

const words = (...all: string[]) => all.filter(Boolean).join(" ");

const merge = (a: Drawn, b: Drawn): Drawn => ({
  actor: words(a.actor, b.actor),
  target: words(a.target, b.target),
  third: words(a.third, b.third),
  ghosts: { ...a.ghosts, ...b.ghosts },
  marks: a.marks + b.marks,
  place: { ...a.place, ...b.place },
  steps: { ...a.steps, ...b.steps },
});

/** Everything one moment says, in the ratified language: every shift it
 * carries and its move, together (R-0526). `third` is the other point of a
 * triangle, which inside and outside both need. */
export function draw(
  kind: string | null,
  actor: Figure,
  target: Figure | null,
  shifts: { symptom: string | null; anxiety: string | null; functioning: string | null },
  third: Figure | null = null,
): Drawn {
  return [
    move(kind, actor, target, third),
    shifts.anxiety
      ? {
          ...NONE,
          actor: "anx pshake",
          ghosts: { actor: "solo" as const },
          marks: spikes(actor, "solo"),
        }
      : NONE,
    shifts.symptom
      ? {
          ...NONE,
          actor: "sym",
          marks: cross(actor, shifts.symptom as Shift),
        }
      : NONE,
    shifts.functioning
      ? { ...NONE, marks: functioning(actor, shifts.functioning as Shift) }
      : NONE,
  ].reduce(merge);
}

function move(
  kind: string | null,
  actor: Figure,
  target: Figure | null,
  third: Figure | null,
): Drawn {
  const pair = target ? frame(actor, target) : null;
  switch (kind) {
    case Move.Toward: {
      if (!target || !pair) return NONE;
      const u = unit(actor, target);
      const go = pair.length - rad(actor) - rad(target) - 7;
      return {
        ...NONE,
        marks: pair.open + arrow(pair, actor, target, false) + pair.close,
        steps: {
          [actor.id]: walk(u.x * go, u.y * go, [0, 0, 1, 1], "0;.06;.5;1", "8s"),
        },
      };
    }
    case Move.Away: {
      if (!target || !pair) return NONE;
      const u = unit(actor, target);
      // the walk keeps its ratified length, scaled to the board, and the mover
      // stands far enough in that it and the arrow ahead of it both fit
      const go = 68 * wide(actor);
      const lead = go + 56 * wide(actor);
      const [stood, shift] = stoodBack(actor, -u.x * lead, -u.y * lead);
      const local = frame(stood, target);
      return {
        ...NONE,
        marks: local.open + arrow(local, stood, target, true, go) + local.close,
        place: shift[0] || shift[1] ? { [actor.id]: shift } : {},
        steps: {
          [actor.id]: walk(-u.x * go, -u.y * go, [0, 0, 1, 1, 1], "0;.06;.5;.94;1", "8s"),
        },
      };
    }
    case Move.Distance:
      return target && pair
        ? {
            ...NONE,
            actor: "tremble10",
            marks: pair.open + wall(pair, actor, false) + pair.close,
          }
        : NONE;
    case Move.Cutoff:
      // the actor never disappears: they tremble while exposed and go still
      // only once the wall shelters them
      return target && pair
        ? {
            ...NONE,
            actor: "tremble10",
            marks: pair.open + wall(pair, actor, true) + pair.close,
          }
        : NONE;
    case Move.Conflict:
      return target && pair
        ? {
            ...NONE,
            actor: "buzz",
            target: "buzz rev",
            marks: pair.open + sparks(pair, actor, target) + pair.close,
          }
        : NONE;
    case Move.DefinedSelf:
      // plain ink while battered, THE green at the moment of stillness, and
      // the other party's storm dies down only a beat later
      return target
        ? {
            ...NONE,
            actor: "dself",
            target: "btrem2",
            marks:
              storm(target) +
              `<circle class="mv-clear" cx="${n1(actor.x)}" cy="${n1(actor.y)}" ` +
              `r="20" opacity="0">` +
              // on the board the one who holds still clears once they have; where
              // the people stay put the clearing keeps coming, from the start
              (actor.still
                ? `<animate attributeName="r" values="18;120" dur="${s_(SPEED.ring)}" repeatCount="indefinite"/>` +
                  `<animate attributeName="opacity" values=".95;0" dur="${s_(SPEED.ring)}" repeatCount="indefinite"/>`
                : `<animate attributeName="r" values="18;120" dur="${s_(SPEED.ring)}" begin="3.2s;11.2s"/>` +
                  `<animate attributeName="opacity" values=".95;0" dur="${s_(SPEED.ring)}" begin="3.2s;11.2s"/>`) +
              `</circle>`,
          }
        : { ...NONE, actor: "dself" };
    case Move.Fusion: {
      if (!target || !pair) return NONE;
      const u = unit(actor, target);
      // the two close right up, but not so far that they cover the bands: the
      // ratified shapes are unfilled, the board's are not
      const gap = rad(actor) + rad(target) + 14;
      const close = Math.max(0, (pair.length - gap) / 2);
      return {
        ...NONE,
        actor: "fused",
        target: "fused",
        marks: pair.open + bands(pair, actor, target, close) + pair.close,
        steps: {
          [actor.id]: walk(u.x * close, u.y * close, [0, 0, 1, 1], "0;.2;.55;1", "8s"),
          [target.id]: walk(-u.x * close, -u.y * close, [0, 0, 1, 1], "0;.2;.55;1", "8s"),
        },
      };
    }
    case Move.Inside: {
      // the mover closes in on the one they want; the same motion pushes the
      // old insider out
      if (!target) return NONE;
      const u = unit(actor, target);
      const join = Math.max(0, u.length - (rad(actor) + rad(target) - 12));
      const steps: Record<number, Walk> = {
        [actor.id]: walk(u.x * join, u.y * join, [0, 0, 1, 1], "0;.2;.55;1", "8s"),
      };
      if (third) {
        const out = unit(target, third);
        steps[third.id] = walk(out.x * 42, out.y * 42, [0, 0, 1, 1], "0;.2;.55;1", "8s");
      }
      return { ...NONE, actor: "joining", steps };
    }
    case Move.Outside: {
      // the heat is between the mover and both of them, and it ends with the
      // walk: no tension is drawn once they have gone
      if (!target) return NONE;
      const others = third ? [target, third] : [target];
      const away = others.reduce(
        (acc, o) => ({ x: acc.x + (actor.x - o.x), y: acc.y + (actor.y - o.y) }),
        { x: 0, y: 0 },
      );
      const len = Math.hypot(away.x, away.y) || 1;
      // the ratified bail-out, scaled to the board, with the mover stood far
      // enough in to take the whole of it
      const go = 55 * wide(actor);
      const step: [number, number] = [(away.x / len) * go, (away.y / len) * go];
      const [stood, shift] = stoodBack(actor, step[0], step[1]);
      return {
        ...NONE,
        actor: "tremout",
        marks:
          `<g class="tenspre">` +
          others.map((o) => zigzag(stood, o, "mv-tension spark")).join("") +
          `</g>`,
        place: shift[0] || shift[1] ? { [actor.id]: shift } : {},
        steps: {
          [actor.id]: walk(step[0], step[1], [0, 0, 1, 1], "0;.32;.55;1", "10s"),
        },
      };
    }
    case Move.Overfunctioning:
      return target
        ? {
            ...NONE,
            actor: "domup",
            target: "subdown",
            marks: flank(actor, true) + flank(target, false),
          }
        : { ...NONE, actor: "domup", marks: flank(actor, true) };
    case Move.Underfunctioning:
      return target
        ? {
            ...NONE,
            actor: "subdown",
            target: "domup",
            marks: flank(actor, false) + flank(target, true),
          }
        : { ...NONE, actor: "subdown", marks: flank(actor, false) };
    case Move.Projection:
      // anxiety uses one language everywhere: it drains off the parent along
      // the arrow's own dashes and settles on the child
      return target
        ? {
            ...NONE,
            // the child inherits the identical shake under its own name
            actor: "proj pshake",
            target: "proj cshake",
            ghosts: { actor: "out", target: "in" },
            marks: spikes(actor, "out") + drainArrow(actor, target) + spikes(target, "in"),
          }
        : {
            ...NONE,
            actor: "proj pshake",
            ghosts: { actor: "solo" },
            marks: spikes(actor, "solo"),
          };
    default:
      return NONE;
  }
}

/** Functioning: down, the outline breaks into borrowed pieces and loses its
 * colour; up, one continuous line of their own, in THE green. */
function functioning(person: Figure, direction: Shift): string {
  const r = rad(person);
  // the ratified 106 for r=17 is the circumference truncated, not rounded
  const circumference = Math.floor(2 * Math.PI * r);
  if (direction === Shift.Up)
    return (
      `<circle class="mv-func up" cx="${n1(person.x)}" cy="${n1(person.y)}" r="${r}"/>`
    );
  return (
    `<circle class="mv-func down" cx="${n1(person.x)}" cy="${n1(person.y)}" r="${r}">` +
    animate(
      "stroke-dasharray",
      `${circumference} 0;${circumference} 0;5 6;5 6;${circumference} 0;${circumference} 0`,
      "0;.12;.34;.58;.8;1",
      "8s",
    ) +
    `</circle>`
  );
}

/** Where the people stand while a move plays: a ring, which is the simple
 * circular layout the 2026-09-02 ruling asked to keep. */
export function ring(
  people: { id: number; name: string; gender?: string | null }[],
  width: number,
  cy: number,
  r = R,
  height = cy * 2,
  /** How much the ring is flattened. A closed triangle keeps its height, or it
   * reads as a squashed ring rather than a figure. */
  flat = 0.62,
): Figure[] {
  const radius = Math.min(78, Math.max(46, width / 2 - 74));
  const place = (p: (typeof people)[number], x: number, y: number): Figure => ({
    ...p,
    x,
    y,
    r,
    mirror: x > width / 2,
    stage: { w: width, h: height },
  });
  if (people.length === 1) return [place(people[0], width / 2, cy)];
  if (people.length === 2)
    return people.map((p, i) =>
      place(p, width / 2 + (i === 0 ? -radius : radius), cy),
    );
  return people.map((p, i) => {
    const angle = -Math.PI / 2 + (i / people.length) * Math.PI * 2;
    return place(
      p,
      width / 2 + Math.cos(angle) * radius,
      cy + Math.sin(angle) * radius * flat,
    );
  });
}
