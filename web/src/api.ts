import type {
  InteractionKind,
  ItemKind,
  PlayReply,
  Reply,
  Statement,
  Timeline,
  TimelineEvent,
} from "./types";

const ROOT = "/companion";

function csrf(): string {
  return (
    document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? ""
  );
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(ROOT + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrf(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${method} ${path}: ${await response.text()}`);
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const timeline = () => call<Timeline>("GET", "/timeline");

export const say = (statement: string) =>
  call<Reply>("POST", "/chat", { statement });

export const play = (clusterId: string) =>
  call<PlayReply>("POST", "/play", { cluster_id: clusterId });

/** Every tap is learning data (R-0077), including the looks that send nothing.
 * A tap with no item in view is still about the record, so it is stored against
 * the diagram itself rather than dropped. */
export const record = (
  diagramId: number,
  kind: InteractionKind,
  itemKind: ItemKind,
  itemId: string | null = null,
) =>
  call<void>("POST", "/interactions", {
    diagram_id: diagramId,
    kind,
    item_kind: itemKind,
    item_id: itemId,
  });

export const session = (id: number) =>
  call<{ statements: Statement[] }>("GET", `/sessions/${id}`);

export const saveEvent = (id: number | null, body: Partial<TimelineEvent>) =>
  id === null
    ? call<TimelineEvent>("POST", "/events", body)
    : call<TimelineEvent>("PATCH", `/events/${id}`, body);

export const deleteEvent = (id: number) => call<void>("DELETE", `/events/${id}`);
