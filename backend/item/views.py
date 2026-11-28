from .models import Item, ItemMembership
from .serializers import UploadItemCSVSerializer, ItemSerializer, NextItemResponseSerializer
from labeling.models import Labeling, LabelingMembership, LabelingSection
from answer.models import Answer, BackgroundAnswer
from user.models import UserGroup
from user.permissions import IsAdminAccount
from labeling.permissions import CanEditLabelingPermission, can_annotate_labeling
from labeling import parts

from datetime import timedelta
import csv
import io
import json
import pandas as pd

from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.shortcuts import get_object_or_404
from django.db.models import Count, Exists, F, OuterRef, Q, Value
from django.db.models.functions import Coalesce
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from django.utils.text import slugify



class ListItemsView(ListAPIView):
    # Items carry vote counts (decision_payload): labeling edit roles and
    # admin accounts only. Annotators are served items by NextItemView.
    permission_classes = [IsAdminAccount | CanEditLabelingPermission]
    serializer_class = ItemSerializer

    def get_queryset(self):
        labeling_id = self.kwargs.get("labeling_id")
        return Item.objects.filter(labeling_id=labeling_id).distinct()


class ImportItemsCsvView(APIView):
    permission_classes = [IsAdminAccount, CanEditLabelingPermission]
    parser_classes = (MultiPartParser,)
    @extend_schema(
        request=UploadItemCSVSerializer,
        responses={
            200: OpenApiResponse(description="Arquivo CSV recebido com sucesso"),
            400: OpenApiResponse(description="Erro na validação ou no arquivo enviado"),
        },
    )
    @transaction.atomic
    def put(self, request, labeling_id):
        labeling = get_object_or_404(Labeling.objects.select_for_update(), id=labeling_id)
        existing_items = list(labeling.items.select_for_update()[:2])
        placeholder = None
        # Form mode starts with one empty item. The first CSV may replace it
        # until an annotator opens or answers it.
        if labeling.form_mode and not labeling.column_names and len(existing_items) == 1:
            candidate = existing_items[0]
            if (
                candidate.row_index == 0
                and candidate.status == "pending"
                and candidate.payload == {}
                and not candidate.memberships.exists()
                and not candidate.answers.exists()
            ):
                placeholder = candidate
        if (existing_items and placeholder is None) or labeling.background_answers.exists():
            return Response(
                {
                    "detail": "Esta rotulação já tem registros importados. Use a opção de adicionar registros.",
                    "code": "ITEMS_ALREADY_IMPORTED",
                },
                status=409,
            )

        serializer = UploadItemCSVSerializer(data=request.data)
        if not serializer.is_valid():
            _discard_failed_import(labeling)
            return Response(serializer.errors, status=400)

        uploaded_file = serializer.validated_data['file']

        # The labeling is created by a previous request. Any failure here must remove it,
        # otherwise it lingers empty and a retry creates a duplicate.
        if uploaded_file is None:
            _discard_failed_import(labeling)
            return Response({"detail": "Nenhum arquivo enviado"}, status=400)

        if not getattr(uploaded_file, "name", "").lower().endswith(".csv"):
            _discard_failed_import(labeling)
            return Response({"detail": "O arquivo deve ser .csv"}, status=400)

        try:
            df = pd.read_csv(uploaded_file, dtype=str)
        except Exception:
            _discard_failed_import(labeling)
            return Response(
                {"detail": "Não foi possível ler o arquivo CSV. Verifique o conteúdo e envie novamente."},
                status=400,
            )

        df.fillna("Valor Nulo", inplace=True)

        cols = df.columns

        if labeling.distribution_strategy == Labeling.DistributionStrategy.PER_PERSON:
            if "user_id" not in cols:
                _discard_failed_import(labeling)
                return Response({"detail": "Para a estratégia 'Por pessoa', o arquivo CSV deve conter uma coluna 'user_id' com os IDs dos usuários."}, status=400)


        labeling.column_names = list(cols)
        labeling.save()

        # A row with more columns than the header does not fail the parsing above:
        # pandas turns the extra leading column into the index, and only the insert
        # below rejects it. Guard here too, so no failure leaves the labeling behind.
        try:
            items = []

            for idx, row in df.iterrows():
                items.append(
                    Item(
                        labeling=labeling,
                        row_index=idx,
                        payload=row.to_dict(),
                        status="pending",
                    )
                )

            with transaction.atomic():
                if placeholder is not None:
                    placeholder.delete()
                Item.objects.bulk_create(items)
        except Exception:
            _discard_failed_import(labeling)
            return Response(
                {"detail": "Não foi possível importar as linhas do arquivo. Verifique se todas as linhas têm o mesmo número de colunas do cabeçalho."},
                status=400,
            )

        return Response({"detail": "Arquivo recebido"}, status=200)

class AddItemsToExistingLabelingView(APIView):
    permission_classes = [IsAdminAccount, CanEditLabelingPermission]
    parser_classes = (MultiPartParser,)
    @extend_schema(
        request=UploadItemCSVSerializer,
        responses={
            200: OpenApiResponse(description="Itens adicionados a rotulação com sucesso"),
            400: OpenApiResponse(description="Erro na validação ou no arquivo enviado"),
        },
    )
    @transaction.atomic
    def post(self, request, labeling_id):
        labeling = get_object_or_404(Labeling.objects.select_for_update(), id=labeling_id)

        columns_in_labeling = labeling.column_names if isinstance(labeling.column_names, list) else []

        serializer = UploadItemCSVSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        uploaded_file = serializer.validated_data['file']

        if uploaded_file is None:
            return Response({"detail": "Nenhum arquivo enviado"}, status=400)

        if not getattr(uploaded_file, "name", "").lower().endswith(".csv"):
            return Response({"detail": "O arquivo deve ser .csv"}, status=400)
        
        df = pd.read_csv(uploaded_file, dtype=str)
        #TODO need to check whether duplicate column names in the upload would cause problems...
        cols = list(df.columns)
        non_existent_cols = columns_in_labeling.copy()
        for col in cols:
            if col not in columns_in_labeling:
                df.drop(columns=[col], inplace=True)
            else:
                non_existent_cols.remove(col)

        if df.empty:
            return Response({"detail": "Nenhum item válido encontrado no arquivo CSV. Verifique se as colunas correspondem às colunas da rotulação."}, status=400)

        for col in non_existent_cols:
            df[col] = "Valor Nulo"

        df.fillna("Valor Nulo", inplace=True)

        if labeling.distribution_strategy == Labeling.DistributionStrategy.PER_PERSON:
            if "user_id" not in cols:
                return Response({"detail": "Para a estratégia 'Por pessoa', o arquivo CSV deve conter uma coluna 'user_id' com os IDs dos usuários."}, status=400)
            
        existing_count = Item.objects.filter(labeling=labeling).count()
        items = []

        for idx, row in df.iterrows():
            items.append(
                Item(
                    labeling=labeling,
                    row_index=existing_count + idx,
                    payload=row.to_dict(),
                    status="pending",
                )
            )

        Item.objects.bulk_create(items)

        if labeling.status == "finished" and len(items) > 0:
            labeling.status = "in_progress"
            labeling.save()
        
        return Response({"detail": "Itens adicionados a rotulação com sucesso"}, status=200)

class ExportImportedItemsCsvView(APIView):
    permission_classes = [IsAdminAccount, CanEditLabelingPermission]

    @extend_schema(
        responses={
            200: OpenApiResponse(description="CSV original reconstruído com sucesso"),
            400: OpenApiResponse(description="Rotulação sem colunas importadas para exportação"),
        },
    )
    def get(self, request, labeling_id):
        labeling = get_object_or_404(Labeling, id=labeling_id)
        columns = labeling.column_names if isinstance(labeling.column_names, list) else []

        if not columns:
            return Response(
                {
                    "detail": "Esta rotulação não possui colunas importadas para exportação.",
                    "code": "IMPORTED_CSV_UNAVAILABLE",
                },
                status=400,
            )

        items = Item.objects.filter(labeling=labeling).order_by("row_index", "id")
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(columns)

        for item in items:
            payload = item.payload or {}
            row = []
            for column in columns:
                value = payload.get(column, "")
                if value is None:
                    row.append("")
                elif isinstance(value, (dict, list)):
                    row.append(json.dumps(value, ensure_ascii=False))
                else:
                    row.append(value)
            writer.writerow(row)

        filename_base = slugify(labeling.title) or f"labeling_{labeling.id}"
        response = HttpResponse(
            buffer.getvalue(),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{filename_base}_imported.csv"'
        )
        return response
    

def _discard_failed_import(labeling):
    """The labeling is created by the request before the upload; a failed first upload
    removes it so a retry doesn't duplicate it. Never when it already holds records
    (Parte 1's placeholder) or answers: then only the upload is refused."""
    from labeling.data_guards import labelings_have_answers
    if not labeling.items.exists() and not labelings_have_answers([labeling.id]):
        labeling.delete()


# A reservation (ItemMembership) is "fresh" while it was renewed within this window. The
# answer page renews it every few minutes while open (see ItemReservationView), so a
# stale reservation means the record was left for longer than this.
RESERVATION_MINUTES = 30


def _fresh_since():
    return timezone.now() - timedelta(minutes=RESERVATION_MINUTES)


def _groups_by_user(user_ids):
    from user.models import UserGroupMembership
    out = {uid: set() for uid in user_ids}
    for uid, name in UserGroupMembership.objects.filter(user_id__in=user_ids).values_list('user_id', 'group__name'):
        out.setdefault(uid, set()).add(name)
    return out


def _decision_slot_open(labeling, item, answer_count, remaining, reserver_groups, user_group_names):
    """Decision mode: may one more annotator (with `user_group_names`) take `item`?

    Fresh reservations of other people count like answers: against users_per_item and,
    with group quotas, against the slot each reserver would fill (own group first, else
    'any', as Item.pick_responded_as_for does). So everyone who holds a fresh reservation
    can still submit. During a tiebreak (votes complete, no winner) one extra voter at a time."""
    if answer_count < labeling.users_per_item:
        if answer_count + len(reserver_groups) >= labeling.users_per_item:
            return False
    elif reserver_groups:
        return False
    if not labeling.has_group_quotas:
        return True
    left = dict(remaining)
    for groups in reserver_groups:
        own = [g for g in groups if left.get(g, 0) > 0]
        if own:
            left[max(own, key=left.get)] -= 1
        elif left.get('any', 0) > 0:
            left['any'] -= 1
    return Item._slot_open({k: v for k, v in left.items() if v > 0}, user_group_names)


def decision_open_for(labeling, items, user, user_group_names):
    """{item_id: bool} for decision-mode items, counting other people's fresh reservations."""
    items = list(items)
    if not items:
        return {}
    ids = [it.id for it in items]
    answers = dict(
        Answer.objects.filter(item_id__in=ids).values('item_id').annotate(n=Count('id')).values_list('item_id', 'n')
    )
    reservations = list(
        ItemMembership.objects.filter(item_id__in=ids, last_seen_at__gte=_fresh_since())
        .exclude(user=user).values_list('item_id', 'user_id')
    )
    groups = _groups_by_user({uid for _, uid in reservations}) if labeling.has_group_quotas else {}
    reservers = {}
    for item_id, uid in reservations:
        reservers.setdefault(item_id, []).append(groups.get(uid, set()))
    remaining = Item.remaining_groups_for(labeling, items) if labeling.has_group_quotas else {}
    return {
        it.id: _decision_slot_open(labeling, it, answers.get(it.id, 0), remaining.get(it.id, {}),
                                   reservers.get(it.id, []), user_group_names)
        for it in items
    }


class NextItemView(RetrieveAPIView):
    serializer_class = NextItemResponseSerializer

    def serialize_and_return(self, item):
        serializer = self.get_serializer(item)
        data = dict(serializer.data)
        # The annotator's own progress (counted before this item), for the header.
        data['progress'] = parts.progress(item.labeling, self.request.user)
        return Response(data, status=200)

    def ensure_membership(self, item, user):
        membership, created = ItemMembership.objects.get_or_create(item=item, user=user)
        if not created:
            # Renews the reservation; last_seen_at is auto_now, so an empty save is enough.
            membership.save(update_fields=['last_seen_at'])
        return membership

    def _user_group_names(self, user):
        """Set of the user's groups, computed once per request."""
        return set(
            UserGroup.objects
            .filter(memberships__user=user)
            .values_list('name', flat=True)
        )

    def _pick_auto_candidate(self, labeling, user, *, require_capacity, user_group_names):
        """
        Picks the best pending item for the user under the automatic strategy.

        Orders by most-answered (to push items toward completion), with
        randomization as a tie-break. `require_capacity=True` requires an
        item that isn't full yet (total_count < users_per_item) — used
        outside decision mode.

        Without group quotas, uses the fast path (.first()). With named group
        quotas, computes the remaining count for all candidates in a single
        aggregated query (Item.remaining_groups_for) and returns, in order,
        the first item where the user can still fill an open group.
        """
        qs = (
            Item.objects
            .filter(labeling=labeling, status='pending')
            .exclude(answers__answered_by=user)
            .annotate(
                answer_count=Count('answers', distinct=True),
                membership_count=Count('memberships', distinct=True),
                total_count=F('answer_count') + F('membership_count'),
            )
        )
        if require_capacity:
            qs = qs.filter(total_count__lt=labeling.users_per_item)
        qs = qs.order_by('-answer_count', '?')

        if not labeling.has_group_quotas:
            return qs.first()

        candidates = list(qs)
        remaining_by_item = Item.remaining_groups_for(labeling, candidates)
        for item in candidates:
            if Item._slot_open(remaining_by_item.get(item.id, {}), user_group_names):
                return item
        return None

    def _steal_stale_membership(self, labeling, user, user_group_names):
        """
        Steals the oldest expired membership from another user (a reservation
        that timed out), respecting group quotas when configured.
        """
        stale_limit = _fresh_since()

        memberships = list(
            ItemMembership.objects
            .select_for_update(skip_locked=True, of=('item',))
            .select_related('item', 'item__labeling')
            .filter(
                item__labeling=labeling,
                item__status='pending',
                last_seen_at__lt=stale_limit,
            )
            .exclude(user=user)
            .exclude(item__answers__answered_by=user)
            .order_by('last_seen_at')  # steals the most abandoned reservation first
        )

        remaining_by_item = {}
        if labeling.has_group_quotas:
            remaining_by_item = Item.remaining_groups_for(
                labeling, [m.item for m in memberships]
            )

        for membership in memberships:
            candidate = membership.item
            if labeling.has_group_quotas and not Item._slot_open(
                remaining_by_item.get(candidate.id, {}), user_group_names
            ):
                continue
            item = (
                Item.objects
                .select_for_update()
                .filter(pk=candidate.pk)
                .first()
            )
            if not item:
                continue
            membership.delete()
            self.ensure_membership(item, user)
            return item
        return None

    def _get_item_auto_strategy(self, labeling, user):
        """
        Returns the next item for the user, following this order:
        1) Item already in a membership of the user's (incomplete)
        2) New free and eligible item
        3) Another person's item with an expired membership (steal)

        When the labeling has group quotas (items_per_group with named groups
        besides 'any'), only items where the user can still fill an open
        group are offered — see Item.remaining_groups_for / Item._slot_open.
        """
        # 1) Does the user already have an active membership?
        membership = (
            ItemMembership.objects
            .select_for_update(of=('item',))
            .select_related('item')
            .filter(
                user=user,
                item__labeling=labeling,
                item__status='pending',
            )
            .first()
        )
        if membership:
            membership = (
                ItemMembership.objects.select_related('item')
                .filter(pk=membership.pk, item__status='pending').first()
            )
        if membership and labeling.decision and membership.last_seen_at < _fresh_since():
            # Left for a long time: others may have filled the record meanwhile.
            groups = self._user_group_names(user) if labeling.has_group_quotas else set()
            if not decision_open_for(labeling, [membership.item], user, groups)[membership.item_id]:
                membership.delete()
                membership = None
        if membership:
            # Renews the reservation so it isn't stolen while the user stays
            # active (last_seen_at is auto_now, so an empty save is enough).
            membership.save(update_fields=['last_seen_at'])
            return membership.item

        # User's groups: only need to be computed when group quotas apply.
        user_group_names = (
            self._user_group_names(user) if labeling.has_group_quotas else set()
        )

        if labeling.decision == True:
            return self._get_item_decision_mode(labeling, user, user_group_names)

        # 2) Get a new eligible item (with capacity)
        item = self._pick_auto_candidate(
            labeling, user, require_capacity=True, user_group_names=user_group_names
        )
        if item is not None:
            item = (
                Item.objects
                .filter(id=item.id)
                .select_for_update(skip_locked=True)
                .first()
            )
            if item:
                self.ensure_membership(item, user)
                return item

        # 3) Steal another person's expired membership
        return self._steal_stale_membership(labeling, user, user_group_names)

    def _get_item_decision_mode(self, labeling, user, user_group_names):
        """Most-voted open record first (to complete records), random among equals. Never
        hands out a record whose slots are held by other people's fresh reservations and
        never deletes another person's reservation."""
        candidates = list(
            Item.objects.filter(labeling=labeling, status='pending')
            .exclude(answers__answered_by=user)
            .annotate(answer_count=Count('answers', distinct=True))
            .order_by('-answer_count', '?')
        )
        open_map = decision_open_for(labeling, candidates, user, user_group_names)
        for candidate in candidates:
            if not open_map.get(candidate.id):
                continue
            item = Item.objects.select_for_update(skip_locked=True).filter(pk=candidate.pk, status='pending').first()
            if item is None:
                continue  # someone else is taking it right now
            # Recheck under the lock: a reservation may have been committed meanwhile.
            if not decision_open_for(labeling, [item], user, user_group_names)[item.id]:
                continue
            self.ensure_membership(item, user)
            return item
        return None

    def _get_item_form_mode(self, labeling, user):
        item = (
            Item.objects.select_for_update()
            .filter(labeling=labeling)
            .exclude(answers__answered_by=user)
            .order_by('row_index', 'id')
            .first()
        )
        if item:
            self.ensure_membership(item, user)
            return item
        return None

    def _get_item_per_person_strategy(self, labeling, user):
        item = (
            Item.objects
            .annotate(item_user_id=F('payload__user_id'))
            .filter(labeling=labeling, status='pending', item_user_id=user.id)
            .exclude(answers__answered_by=user)
            .order_by('?')
            .first()
        )
        if item:
            self.ensure_membership(item, user)
            return item
        return None

    def get_next_item_for_user(self, labeling, user):

        if labeling.status == "finished":
            return Response(
                {"detail": "Essa rotulação já foi finalizada", "code": "ROTULACAO_FINALIZADA"},
                status=400,
            )

        if labeling.form_mode:
            return self._get_item_form_mode(labeling, user)

        if labeling.distribution_strategy == Labeling.DistributionStrategy.AUTO:
            return self._get_item_auto_strategy(labeling, user)
        elif labeling.distribution_strategy == Labeling.DistributionStrategy.SPECIFIED:
            return Response(
                {"detail": "A estratégia de distribuição 'Estipulada' ainda não é suportada.", "code": "ESTRATEGIA_NAO_SUPORTADA"},
                status=400,
            )
        elif labeling.distribution_strategy == Labeling.DistributionStrategy.PER_PERSON:

            return self._get_item_per_person_strategy(labeling, user)

        return None

    @transaction.atomic
    def retrieve(self, request, *args, **kwargs):
        labeling = get_object_or_404(Labeling, id=kwargs['labeling_id'])
        user = request.user

        if not LabelingSection.objects.filter(
            labeling=labeling,
            form_type=LabelingSection.FormType.MAIN,
        ).exists():
            return Response({'detail':'o formulário dessa rotulação está vazio','code':'EMPTY_FORM'},status=403)

        if not can_annotate_labeling(user, labeling.id):
            return Response('Você não faz parte dessa rotulação',status=403)

        # Joined labelings: the later part opens only once the earlier one is done.
        blocker = parts.blocking_part(labeling, user)
        if blocker is not None:
            return Response(
                {
                    'detail': 'Conclua a parte anterior antes de começar esta.',
                    'code': 'PREVIOUS_PART_REQUIRED',
                    'previous_labeling_id': blocker.id,
                },
                status=403,
            )

        if labeling.has_background_form and not BackgroundAnswer.objects.filter(
            labeling=labeling,
            answered_by=user,
        ).exists():
            return Response(
                {
                    'detail': 'Você precisa responder o formulário background antes de rotular.',
                    'code': 'BACKGROUND_REQUIRED',
                },
                status=403,
            )

        item = self.get_next_item_for_user(labeling, user)
        if isinstance(item, Response):
            return item
        if not item:
            body = {'detail': 'Você não tem mais rotulações para responder.','code':'NO_LABELINGS_TO_ANSWER'}
            nxt = labeling.next_labeling
            if labeling.form_mode and nxt is not None and can_annotate_labeling(user, nxt.id):
                body['next_labeling_id'] = nxt.id
            return Response(body, status=400)

        return self.serialize_and_return(item)



class ItemReservationView(APIView):
    """Heartbeat of the answer page: renews the caller's reservation of `item`, or answers
    409 RESERVATION_LOST when it is gone (or, in decision mode, the record was filled
    while the reservation was stale) so the page can say so before more work is lost."""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, labeling_id):
        labeling = get_object_or_404(Labeling, id=labeling_id)
        item_id = request.data.get('item')
        membership = (
            ItemMembership.objects.select_for_update(of=('item',)).select_related('item')
            .filter(user=request.user, item_id=item_id, item__labeling=labeling).first()
            if str(item_id).isdigit() else None
        )
        if membership:
            membership = ItemMembership.objects.select_related('item').filter(pk=membership.pk).first()
        lost = membership is None or membership.item.status == 'finished'
        if not lost and labeling.decision and not labeling.form_mode and membership.last_seen_at < _fresh_since():
            groups = set(UserGroup.objects.filter(memberships__user=request.user).values_list('name', flat=True))
            if not decision_open_for(labeling, [membership.item], request.user, groups)[membership.item_id]:
                membership.delete()
                lost = True
        if lost:
            return Response({'detail': 'Este registro não está mais reservado para você.',
                             'code': 'RESERVATION_LOST'}, status=409)
        membership.save(update_fields=['last_seen_at'])
        return Response({'item': membership.item_id, 'renewed': True}, status=200)


class AnonymousNextItemView(RetrieveAPIView):
    """
    Public/anonymous variant of NextItemView.

    Identifies the labeling by the anonymous-mode token in the URL (instead
    of labeling_id) and skips authentication and any user/membership check,
    since anonymous annotators don't have an account. Returns the same
    structure: the form's sections and a pending item.
    """
    serializer_class = NextItemResponseSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def serialize_and_return(self, item):
        serializer = self.get_serializer(item)
        return Response(serializer.data, status=200)

    @transaction.atomic
    def retrieve(self, request, *args, **kwargs):
        labeling = get_object_or_404(
            Labeling,
            anonymous_token=kwargs['token'],
            distribution_strategy=Labeling.DistributionStrategy.ANONYMOUS_MODE,
        )

        if labeling.status == "finished":
            return Response(
                {"detail": "Essa rotulação já foi finalizada", "code": "ROTULACAO_FINALIZADA"},
                status=400,
            )

        if not LabelingSection.objects.filter(
            labeling=labeling,
            form_type=LabelingSection.FormType.MAIN,
        ).exists():
            return Response({'detail': 'o formulário dessa rotulação está vazio', 'code': 'EMPTY_FORM'}, status=403)

        # With no user to distinguish requesters, we simply return the next pending item.
        item = (
            Item.objects
            .filter(labeling=labeling, status='pending')
            .order_by('row_index', 'id')
            .first()
        )
        if not item:
            return Response({'detail': 'Não há mais itens para rotular.', 'code': 'NO_LABELINGS_TO_ANSWER'}, status=400)

        return self.serialize_and_return(item)

