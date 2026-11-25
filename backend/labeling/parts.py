"""Joined labelings (Study 1): a form_mode labeling whose `next_labeling` is the
main labeling. Together they appear to annotators as numbered parts.

- The later part stays locked until the user has answered every item of the
  earlier part (otherwise the shared starting items and the consent could be
  skipped by opening the later part directly).
- Each annotator gets their own progress: items they answered, and for a
  form_mode part the total, since everyone answers every item there.
"""
import math

from django.utils import timezone

from answer.models import Answer
from item.models import Item

from .models import Labeling

_MAX_PARTS = 10  # guards against a cycle in next_labeling


def previous_part(labeling):
    return Labeling.objects.filter(next_labeling=labeling).order_by("id").first()


def part_position(labeling):
    """(part number, number of parts), or None for a labeling that is not joined."""
    index, cursor = 1, labeling
    for _ in range(_MAX_PARTS):
        cursor = previous_part(cursor)
        if cursor is None:
            break
        index += 1
    total, cursor = index, labeling
    for _ in range(_MAX_PARTS):
        cursor = cursor.next_labeling
        if cursor is None:
            break
        total += 1
    return None if total == 1 else (index, total)


def items_done(labeling, user):
    return (
        Answer.objects.filter(labeling=labeling, answered_by=user)
        .values("item_id").distinct().count()
    )


def finished_by(labeling, user):
    total = Item.objects.filter(labeling=labeling).count()
    return total > 0 and items_done(labeling, user) >= total


def blocking_part(labeling, user):
    """The earlier form_mode part this user still has to finish, or None."""
    from .permissions import can_annotate_labeling

    prev = previous_part(labeling)
    if prev is None or not prev.form_mode or not can_annotate_labeling(user, prev.id):
        return None
    return None if finished_by(prev, user) else prev


def _goal_part(labeling):
    """This labeling or the first later joined part with an answer target, plus the
    form_mode parts in between (this one included) that must be finished before it."""
    before, cursor = [], labeling
    for _ in range(_MAX_PARTS):
        if cursor.answer_target:
            return cursor, before
        if not cursor.form_mode:
            return None, []
        before.append(cursor)
        cursor = cursor.next_labeling
        if cursor is None:
            return None, []
    return None, []


def next_milestone(done, target, step):
    """The target, or once it is reached the next target + k * step above `done`."""
    if done < target:
        return target
    if not step:
        return target
    return target + step * ((done - target) // step + 1)


def goal(labeling, user, today=None):
    """The annotator's goal toward the target of this (or a later joined) part, with the
    weekly/daily pace until that part's final_date; None when no part sets a target.

    Pace counts the records still missing in earlier form_mode parts plus those missing
    to the target. It is None once the target is reached or final_date has passed (the
    form stays open; moving final_date brings the pace back).
    """
    goal_part, before = _goal_part(labeling)
    if goal_part is None:
        return None
    today = today or timezone.localdate()
    target, step = goal_part.answer_target, goal_part.milestone_step
    done = items_done(goal_part, user)
    before_missing = sum(
        max(Item.objects.filter(labeling=part).count() - items_done(part, user), 0)
        for part in before
    )
    to_go = before_missing + max(target - done, 0)
    days_left = (goal_part.final_date - today).days + 1  # today counts
    per_week = per_day = None
    if to_go > 0 and days_left > 0:
        per_day = math.ceil(to_go / days_left)
        per_week = math.ceil(to_go / math.ceil(days_left / 7))
    return {
        "target": target,
        "done": done,
        "next_milestone": next_milestone(done, target, step),
        "before_missing": before_missing,
        "to_go": to_go,
        "deadline": goal_part.final_date.isoformat(),
        "days_left": max(days_left, 0),
        "per_week": per_week,
        "per_day": per_day,
    }


def progress(labeling, user):
    position = part_position(labeling)
    return {
        "done": items_done(labeling, user),
        "total": Item.objects.filter(labeling=labeling).count() if labeling.form_mode else None,
        "part": position[0] if position else None,
        "parts": position[1] if position else None,
        "goal": goal(labeling, user),
    }
