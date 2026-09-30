import * as api from "./api";
import { Strip } from "./strip";
import { beyond } from "./place";
import { NotificationKind, type Delivery } from "./types";

/** The newest unread notification the thread does not already show: a coach
 * message is in the thread, so it never takes the strip (R-0606, R-0611). */
export const newest = (unread: Delivery[]): Delivery | null =>
  unread.find((one) => one.kind !== NotificationKind.Coach) ?? null;

/** The reader's notifications: one strip at a time for the newest unread, a
 * mark on the account button while a notice is unread, and every notice for
 * the account view's Notices (R-0611). */
export class Notices {
  /** Every notice, opened or not, newest first. */
  list: Delivery[] = [];

  constructor(
    private strip: Strip,
    private account: HTMLElement,
    /** Where a notice's link goes: a fixed screen's name or an address. */
    private go: (link: string) => void,
  ) {}

  async refresh(): Promise<void> {
    const all = await api.notifications(true);
    const unread = all.filter((one) => one.opened_at === null);
    this.list = all.filter((one) => one.kind === NotificationKind.Notice);
    this.account.classList.toggle(
      "unread",
      unread.some((one) => one.kind === NotificationKind.Notice),
    );
    const top = newest(unread);
    if (!top) return this.strip.hide();
    const where = beyond(top.link);
    this.strip.show({
      title: top.title,
      body: top.body,
      open: where ? { label: `Open ${where}`, tap: () => void this.open(top) } : null,
      dismiss: () => void this.open(top, false),
    });
  }

  /** Counted opened, then the screen it points to, unless it was put away. */
  async open(one: Delivery, go = true): Promise<void> {
    await api.openNotification(one.id);
    await this.refresh();
    if (go && one.link) this.go(one.link);
  }
}
