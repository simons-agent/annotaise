import ProgressBar from './ProgressBar';
import { useTranslations } from '@/i18n/use-translations';
import type { AnswerGoal } from '@/modules/labelings/labelingsTypes';
import { goalBar, goalBarLabel, paceLines } from '@/modules/goal/goal';

type GoalBlockProps = {
  goal: AnswerGoal;
  /** Show the bar toward the target; false while the card shows a fixed part (Parte 1). */
  showBar?: boolean;
  bgColor: string;
  fillColor: string;
};

// Study 1 goal on the annotator card: bar toward the target (then the next milestone),
// the weekly pace with the daily figure, and the recognition lines. No ranking.
export default function GoalBlock({ goal, showBar = true, bgColor, fillColor }: GoalBlockProps) {
  const { t, locale } = useTranslations();
  const bar = goalBar(goal);
  const pace = paceLines(goal, t, locale);
  const reached = goal.done >= goal.target;

  return (
    <div className="flex flex-col gap-2 min-w-0 w-full">
      {showBar ? (
        <ProgressBar
          value={bar.value}
          max={bar.max}
          label={goalBarLabel(goal, t)}
          bgColor={bgColor}
          fillColor={fillColor}
          rounded="right"
          className="-ml-3"
        />
      ) : null}
      {pace ? (
        <p className="text-sm leading-snug text-gray-800">
          <span className="font-semibold text-blueberry-700">{pace.week}</span>{' '}
          <span className="text-gray-600">{pace.day}</span>
        </p>
      ) : null}
      <p className="text-xs leading-snug text-gray-600">
        {reached ? t('goal.reached', { target: goal.target }) : t('goal.complete', { target: goal.target })}{' '}
        {t('goal.coauthor')}
      </p>
    </div>
  );
}
