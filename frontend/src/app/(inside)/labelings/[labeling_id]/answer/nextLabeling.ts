/**
 * Study 1: a finished form_mode labeling may point at a follow-up labeling
 * (`next_labeling_id` on the NO_LABELINGS_TO_ANSWER error). Returns the path to
 * redirect to, or null when the normal "nothing left" message applies.
 */
export function nextLabelingRedirect(
  data: { code?: string; next_labeling_id?: unknown } | null | undefined,
): string | null {
  if (data?.code !== 'NO_LABELINGS_TO_ANSWER') return null;
  const id = data.next_labeling_id;
  if (typeof id !== 'number' || !Number.isInteger(id) || id <= 0) return null;
  return `/labelings/${id}/answer`;
}
