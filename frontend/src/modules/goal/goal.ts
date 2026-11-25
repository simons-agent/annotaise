import type { AnswerGoal } from '@/modules/labelings/labelingsTypes';

type T = (key: string, vars?: Record<string, string | number>) => string;

/** "15/12" style day of the deadline (ISO date, no timezone shift). */
export function deadlineLabel(iso: string, locale: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString(locale, {
    day: 'numeric',
    month: 'long',
    timeZone: 'UTC',
  });
}

/** Bar value/max: toward the target, then toward the next milestone. */
export function goalBar(goal: AnswerGoal): { value: number; max: number } {
  return { value: Math.min(goal.done, goal.next_milestone), max: goal.next_milestone };
}

export function goalBarLabel(goal: AnswerGoal, t: T): string {
  return goal.done < goal.target
    ? t('goal.toTarget', { done: goal.done, target: goal.target })
    : t('goal.toMilestone', { done: goal.done, milestone: goal.next_milestone });
}

/** Weekly pace line (with the daily figure), or null when no pace is shown. */
export function paceLines(goal: AnswerGoal, t: T, locale: string): { week: string; day: string } | null {
  if (goal.per_week == null || goal.per_day == null) return null;
  const deadline = deadlineLabel(goal.deadline, locale);
  const week =
    goal.before_missing > 0
      ? t('goal.paceWeekWithPart', { before: goal.before_missing, target: goal.target, perWeek: goal.per_week, deadline })
      : t('goal.paceWeek', { toGo: goal.to_go, perWeek: goal.per_week, deadline });
  return { week, day: t('goal.paceDay', { perDay: goal.per_day }) };
}

/** Compact header text for the answer page. */
export function goalHeaderLabel(goal: AnswerGoal, t: T): string {
  if (goal.done >= goal.target) return t('goal.headerMilestone', { done: goal.done, milestone: goal.next_milestone });
  if (goal.per_week != null) return t('goal.headerWeek', { done: goal.done, target: goal.target, perWeek: goal.per_week });
  return t('goal.header', { done: goal.done, target: goal.target });
}

const YOUTUBE_ID = /(?:youtu\.be\/|youtube\.com\/(?:watch\?(?:[^\s)]*&)?v=|embed\/|shorts\/))([A-Za-z0-9_-]{11})/;

/** Video id of the first YouTube link in a text, or null. */
export function firstYoutubeId(text: string): string | null {
  return text.match(YOUTUBE_ID)?.[1] ?? null;
}
