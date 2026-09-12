import * as api from "./api";
import { esc } from "./dom";
import { TaskKind, type FinishedTask, type Task, type Tasks } from "./types";

/** The coder's one task. One card, one button, and under it a faint record of
 * what is already finished — never a list to choose from (R-0265). What to
 * code comes from what Patrick put on the table. */

export interface TaskHandlers {
  /** Start this task: the conversation opens as the coding screen. */
  onStart(task: Task): void;
  /** A finished task whose cut the room has ratified opens what the meeting
   * produced (R-0275). */
  onResult(cutId: number): void;
}

/** The meeting a task is for, which is what the title row says. */
export function beforeMeeting(task: Task | null): string {
  if (!task?.meeting_date) return "Your task";
  const when = new Date(`${task.meeting_date}T00:00:00`);
  return `Before ${when.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  })}`;
}

const CHECK = "&#10003;";

export class OneTask {
  private task: Task | null = null;

  constructor(
    private body: HTMLElement,
    private handlers: TaskHandlers,
  ) {
    this.body.addEventListener("click", (e) => {
      const start = (e.target as Element).closest(".addbtn");
      if (start && this.task?.ready) {
        this.handlers.onStart(this.task);
        return;
      }
      const done = (e.target as Element).closest<HTMLElement>(".plrow.done");
      if (done?.dataset.result)
        this.handlers.onResult(Number(done.dataset.result));
    });
  }

  /** What the coder has to do now, or nothing when the table is empty. */
  async load(): Promise<Task | null> {
    const found: Tasks = await api.tasks();
    this.task = found.task;
    this.render(found);
    return this.task;
  }

  showing(): Task | null {
    return this.task;
  }

  private render(found: Tasks): void {
    this.body.innerHTML =
      (found.task ? this.card(found.task) : this.nothing()) +
      (found.done.length
        ? `<div class="plprog tkdone">done before</div>` +
          found.done.map((one) => this.finished(one)).join("")
        : "");
  }

  private card(task: Task): string {
    const waiting = task.ready ? "" : " waiting";
    return (
      `<div class="row tkcard${waiting}">` +
      `<div class="r1">${esc(task.title)}</div>` +
      `<div class="r2">${esc(task.detail)}</div>` +
      `<button class="addbtn" type="button"${task.ready ? "" : " disabled"}>` +
      `${task.kind === TaskKind.Vote ? "vote" : "start"}</button></div>`
    );
  }

  private finished(one: FinishedTask): string {
    const opens = one.ratified ? ` data-result="${one.cut_id}"` : "";
    return (
      `<div class="plrow done"${opens}><span class="ck">${CHECK}</span>` +
      `<div class="pm"><div class="r1">${esc(one.title)}</div>` +
      `<div class="r2">${esc(one.detail)}</div></div></div>`
    );
  }

  private nothing(): string {
    return `<div class="none">Nothing is on the table to code yet.</div>`;
  }
}
