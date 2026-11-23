"""Joined labelings (Study 1): a form_mode labeling whose `next_labeling` is the
main labeling. Together they appear to annotators as numbered parts.

- The later part stays locked until the user has answered every item of the
  earlier part (otherwise the shared starting items and the consent could be
  skipped by opening the later part directly).
- Each annotator gets their own progress: items they answered, and for a
  form_mode part the total, since everyone answers every item there.
"""
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


def progress(labeling, user):
    position = part_position(labeling)
    return {
        "done": items_done(labeling, user),
        "total": Item.objects.filter(labeling=labeling).count() if labeling.form_mode else None,
        "part": position[0] if position else None,
        "parts": position[1] if position else None,
    }
