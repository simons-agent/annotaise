"""Refusals that keep collected answers safe from manager actions (Study 1).

Deleting a labeling cascades to its items and answers; deleting a project orphans its
labelings; deleting a user detaches their answers (answered_by becomes NULL, exported as
"anonymous"). Once a labeling has answers these actions answer 409 instead."""
from rest_framework import status
from rest_framework.exceptions import APIException


class DataConflict(APIException):
    status_code = status.HTTP_409_CONFLICT

    def __init__(self, detail, code):
        super().__init__({"detail": detail, "code": code})


def labelings_have_answers(labeling_ids) -> bool:
    from answer.models import Answer, BackgroundAnswer
    ids = list(labeling_ids)
    return (Answer.objects.filter(labeling_id__in=ids).exists()
            or BackgroundAnswer.objects.filter(labeling_id__in=ids).exists())


def refuse_if_labelings_have_answers(labeling_ids, what):
    if labelings_have_answers(labeling_ids):
        raise DataConflict(
            f"{what} já tem respostas coletadas e não pode ser excluído(a). "
            "Exporte os dados e fale com a equipe do estudo.",
            "HAS_ANSWERS",
        )


def refuse_if_user_has_answers(user):
    from answer.models import Answer, BackgroundAnswer
    if Answer.objects.filter(answered_by=user).exists() or BackgroundAnswer.objects.filter(answered_by=user).exists():
        raise DataConflict(
            "Esta conta tem respostas registradas; excluí-la apagaria a autoria dessas respostas. "
            "Desative a conta em vez de excluí-la.",
            "USER_HAS_ANSWERS",
        )
