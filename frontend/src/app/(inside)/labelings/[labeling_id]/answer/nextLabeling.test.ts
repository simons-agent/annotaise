import { describe, expect, it } from 'vitest';
import { nextLabelingRedirect } from './nextLabeling';

describe('nextLabelingRedirect', () => {
  it('redirects to next labeling', () => {
    expect(nextLabelingRedirect({ code: 'NO_LABELINGS_TO_ANSWER', next_labeling_id: 7 })).toBe('/labelings/7/answer');
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
