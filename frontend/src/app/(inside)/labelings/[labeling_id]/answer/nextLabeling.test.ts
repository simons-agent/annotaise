import { describe, expect, it } from 'vitest';
import { nextLabelingRedirect, previousPartRedirect, recordProgressLabel } from './nextLabeling';

const t = (key: string, vars?: Record<string, string | number>) => `${key}:${JSON.stringify(vars ?? {})}`;

describe('nextLabelingRedirect', () => {
  it('redirects to next labeling and flags the finished part', () => {
    expect(nextLabelingRedirect({ code: 'NO_LABELINGS_TO_ANSWER', next_labeling_id: 7 })).toBe('/labelings/7/answer?partDone=1');
  });

  it('shows thank-you without next labeling', () => {
    expect(nextLabelingRedirect({ code: 'NO_LABELINGS_TO_ANSWER' })).toBeNull();
    expect(nextLabelingRedirect({ code: 'NO_LABELINGS_TO_ANSWER', next_labeling_id: null })).toBeNull();
    expect(nextLabelingRedirect(undefined)).toBeNull();
  });

  it('ignores other error codes', () => {
    expect(nextLabelingRedirect({ code: 'ROTULACAO_FINALIZADA', next_labeling_id: 7 })).toBeNull();
  });
});

describe('previousPartRedirect', () => {
  it('sends the annotator back to the unfinished part', () => {
    expect(previousPartRedirect({ code: 'PREVIOUS_PART_REQUIRED', previous_labeling_id: 20 })).toBe('/labelings/20/answer');
  });

  it('ignores other codes and bad ids', () => {
    expect(previousPartRedirect({ code: 'NO_LABELINGS_TO_ANSWER', previous_labeling_id: 20 })).toBeNull();
    expect(previousPartRedirect({ code: 'PREVIOUS_PART_REQUIRED', previous_labeling_id: '20' })).toBeNull();
    expect(previousPartRedirect(undefined)).toBeNull();
  });
});

describe('recordProgressLabel', () => {
  it('counts the current record within a fixed set', () => {
    expect(recordProgressLabel({ done: 3, total: 45 }, t)).toBe('answer.recordProgress:{"current":4,"total":45}');
    expect(recordProgressLabel({ done: 45, total: 45 }, t)).toBe('answer.recordProgress:{"current":45,"total":45}');
  });

  it('counts completed records when the share is not fixed', () => {
    expect(recordProgressLabel({ done: 12, total: null }, t)).toBe('answer.recordsDone:{"done":12}');
  });

  it('returns null without progress', () => {
    expect(recordProgressLabel(undefined, t)).toBeNull();
  });
});
