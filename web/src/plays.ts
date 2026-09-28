import type { Case, Cluster } from "./types";

/** A play-by-play on the thread: the case the coach told, and the digest of
 * the cluster's contents it was told from. */
export interface Kept {
  case: Case;
  digest: string | null;
}

/** A tap on a kept play opens it again while its cluster still holds what it
 * was told from. Otherwise the cluster is explained again, which the server
 * answers from a kept play when one fits, or tells anew. A play kept before
 * digests, or of a cluster the record no longer holds, is explained again. */
export function reopen(
  kept: Kept,
  clusters: Cluster[],
  open: (told: Case) => void,
  explain: (clusterId: string) => void,
): void {
  const now = clusters.find((c) => c.id === kept.case.cluster_id);
  if (kept.digest !== null && now?.digest === kept.digest) open(kept.case);
  else explain(kept.case.cluster_id!);
}
