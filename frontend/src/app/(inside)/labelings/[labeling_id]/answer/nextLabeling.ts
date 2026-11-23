/**
 * Study 1: joined labelings. A finished form_mode labeling points at the
 * follow-up labeling (`next_labeling_id` on the NO_LABELINGS_TO_ANSWER error),
 * and opening the follow-up too early points back at the unfinished one
 * (`previous_labeling_id` on PREVIOUS_PART_REQUIRED).
 */

/** Query flag set when moving on from a finished part, so the next page can say so. */
export const PART_DONE_PARAM = 'partDone';

function validId(id: unknown): id is number {
  return typeof id === 'number' && Number.isInteger(id) && id > 0;
}

/** Path to continue in once this part is finished, or null for the normal "nothing left" message. */
export function nextLabelingRedirect(
  data: { code?: string; next_labeling_id?: unknown } | null | undefined,
): string | null {
  if (data?.code !== 'NO_LABELINGS_TO_ANSWER') return null;
  const id = data.next_labeling_id;
  if (!validId(id)) return null;
  return `/labelings/${id}/answer?${PART_DONE_PARAM}=1`;
}

/** Path of the earlier part the annotator still has to finish, or null. */
export function previousPartRedirect(
  data: { code?: string; previous_labeling_id?: unknown } | null | undefined,
): string | null {
  if (data?.code !== 'PREVIOUS_PART_REQUIRED') return null;
  const id = data.previous_labeling_id;
  if (!validId(id)) return null;
  return `/labelings/${id}/answer`;
}

/** Header text for the annotator's position: "Registro 4 de 45", or "12 registros concluídos". */
export function recordProgressLabel(
  progress: { done: number; total: number | null } | null | undefined,
  t: (key: string, vars?: Record<string, string | number>) => string,
): string | null {
  if (!progress) return null;
  if (progress.total) {
    return t('answer.recordProgress', { current: Math.min(progress.done + 1, progress.total), total: progress.total });
  }
  return t('answer.recordsDone', { done: progress.done });
}

/** Path of this labeling's background (profile) form when it must be answered first, or null. */
export function backgroundRedirect(
  data: { code?: string } | null | undefined,
  labelingId: number,
): string | null {
  if (data?.code !== 'BACKGROUND_REQUIRED' || !validId(labelingId)) return null;
  return `/labelings/${labelingId}/background`;
}
