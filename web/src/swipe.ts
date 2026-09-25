/** Swipe a row left and its actions come out from behind it; swipe it back, or
 * tap anywhere else, and they go away. The list scrolls vertically, so only a
 * drag that is more across than down is a swipe. The ratified gesture of the
 * sessions sheet, shared by every list that has one. */

/** How far a row travels before its actions show. */
const SWIPE_PX = 72;

export class Swipe {
  /** The row whose actions are showing, if any. */
  swiped: HTMLElement | null = null;
  /** True between the swipe revealing the actions and the click it ends with. */
  private opening = false;

  constructor(
    body: HTMLElement,
    private rows: string,
    /** The action buttons for one row, and a class the row wears while they
     * show, for a row with more of them than fit the usual width. Null for a
     * row that draws its own actions behind it. */
    private actions: (row: HTMLElement) => { html: string; wide: boolean } | null,
  ) {
    let from: { x: number; y: number; row: HTMLElement } | null = null;
    body.addEventListener("pointerdown", (e) => {
      const row = (e.target as Element).closest<HTMLElement>(this.rows);
      if (!row || (e.target as Element).closest(".fs-act")) return;
      from = { x: e.clientX, y: e.clientY, row };
    });
    body.addEventListener("pointermove", (e) => {
      if (!from) return;
      const dx = e.clientX - from.x;
      if (Math.abs(dx) <= Math.abs(e.clientY - from.y)) return;
      if (dx <= -SWIPE_PX) {
        this.open(from.row);
        from = null;
      } else if (dx >= SWIPE_PX && this.swiped === from.row) {
        this.close();
        from = null;
      }
    });
    for (const kind of ["pointerup", "pointercancel"])
      body.addEventListener(kind, () => {
        from = null;
      });
  }

  /** Show one row's actions: by the swipe itself, whose click is still to
   * come, or by a tap on a button that has no click after it. */
  open(row: HTMLElement, bySwipe = true): void {
    if (this.swiped === row) return;
    this.close();
    const acts = this.actions(row);
    if (acts)
      row.insertAdjacentHTML(
        "beforeend",
        `<div class="fs-acts${acts.wide ? " wide" : ""}">${acts.html}</div>`,
      );
    row.classList.add("swiped");
    if (acts?.wide) row.classList.add("wide");
    this.swiped = row;
    this.opening = bySwipe;
  }

  /** The row's actions out if they are away, away if they are out: what a
   * button beside the row does. */
  toggle(row: HTMLElement): void {
    if (this.swiped === row) this.close();
    else this.open(row, false);
  }

  close(): void {
    if (!this.swiped) return;
    this.swiped.classList.remove("swiped", "wide");
    this.swiped.querySelector(".fs-acts")?.remove();
    this.swiped = null;
  }

  /** Whether a click on the list belongs to the swipe rather than to the row
   * under it: the click the revealing gesture ends with, or a tap that puts
   * open actions away. */
  claims(): boolean {
    if (this.opening) {
      this.opening = false;
      return true;
    }
    if (!this.swiped) return false;
    this.close();
    return true;
  }

  /** The list was drawn again, so no row has its actions out. */
  forget(): void {
    this.swiped = null;
  }
}
