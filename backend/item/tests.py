from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from project.models import Project
from project.models import ProjectMembership
from labeling.models import Labeling, LabelingMembership
from .models import Item
from .serializers import ItemSerializer
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
import csv
import io

class ItemSerializerTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="testuser", password="pass")
        self.project = Project.objects.create(name="Test Project", created_by=self.user)
        self.labeling = Labeling.objects.create(
            project=self.project,
            title="Test Labeling",
            created_by=self.user,
            start_date=timezone.now().date(),
            final_date=timezone.now().date(),
        )
        self.item = Item.objects.create(labeling=self.labeling, payload={"a": 1}, row_index=0)

    def test_serialization_success(self):
        ser = ItemSerializer(self.item)
        self.assertEqual(ser.data["labeling"], self.labeling.id)
        self.assertEqual(ser.data["payload"], {"a": 1})
        self.assertEqual(ser.data["row_index"], 0)

    def test_deserialization_success(self):
        payload = {
            "id": 999,                # should be ignored (read-only)
            "labeling": self.labeling.id,
            "payload": {"b": 2},
            "row_index": 1
        }
        ser = ItemSerializer(data=payload)
        self.assertTrue(ser.is_valid(), ser.errors)
        obj = ser.save()
        self.assertNotEqual(obj.id, 999)

    def test_deserialization_failure_missing_labeling(self):
        bad = {
            "payload": {"b": 2},
            "row_index": 1
        }
        ser = ItemSerializer(data=bad)
        self.assertFalse(ser.is_valid())
        self.assertIn("labeling", ser.errors)

    def test_deserialization_failure_invalid_payload(self):
        bad = {
            "labeling": self.labeling.id,
            "payload": "not a dict",
            "row_index": 1
        }
        ser = ItemSerializer(data=bad)
        self.assertFalse(ser.is_valid())
        self.assertIn("payload", ser.errors)


class ExportImportedItemsCsvViewTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="item_owner",
            password="pass123",
            email="owner@example.com",
            account_type="admin",
        )
        self.outsider = User.objects.create_user(
            username="item_outsider",
            password="pass123",
            email="outsider@example.com",
            account_type="admin",
        )

        self.project = Project.objects.create(
            name="Export Project",
            description="project for csv export",
            created_by=self.owner,
        )
        ProjectMembership.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMembership.RoleChoices.OWNER,
        )

        self.labeling = Labeling.objects.create(
            project=self.project,
            title="CSV Importado",
            created_by=self.owner,
            start_date=timezone.now().date(),
            final_date=timezone.now().date(),
            column_names=["id_externo", "texto", "observacao"],
        )

        LabelingMembership.objects.create(
            labeling=self.labeling,
            user=self.owner,
            role=LabelingMembership.Role.OWNER,
        )

        Item.objects.create(
            labeling=self.labeling,
            row_index=1,
            payload={
                "id_externo": 2,
                "texto": 'linha com "aspas"',
                "observacao": "segunda linha",
            },
            status="pending",
        )
        Item.objects.create(
            labeling=self.labeling,
            row_index=0,
            payload={
                "id_externo": 1,
                "texto": "linha, com virgula",
                "observacao": "primeira linha",
            },
            status="pending",
        )

        self.client = APIClient()
        self.url = reverse("export-imported-items-csv", args=[self.labeling.id])

    def test_owner_can_download_reconstructed_imported_csv(self):
        self.client.force_authenticate(self.owner)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("csv-importado_imported.csv", response["Content-Disposition"])

        content = response.content.decode("utf-8")
        rows = list(csv.reader(io.StringIO(content)))

        self.assertEqual(rows[0], ["id_externo", "texto", "observacao"])
        self.assertEqual(
            rows[1],
            ["1", "linha, com virgula", "primeira linha"],
        )
        self.assertEqual(
            rows[2],
            ["2", 'linha com "aspas"', "segunda linha"],
        )

    def test_admin_without_project_permission_cannot_download_csv(self):
        self.client.force_authenticate(self.outsider)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ImportItemsCsvViewTest(TestCase):
    """The labeling is created by a previous request, so a failed import must not leave it behind."""

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="import_owner",
            password="pass123",
            email="import_owner@example.com",
            account_type="admin",
        )

        self.project = Project.objects.create(
            name="Import Project",
            description="project for csv import",
            created_by=self.owner,
        )
        ProjectMembership.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMembership.RoleChoices.OWNER,
        )

        self.labeling = Labeling.objects.create(
            project=self.project,
            title="CSV a importar",
            created_by=self.owner,
            start_date=timezone.now().date(),
            final_date=timezone.now().date(),
        )
        LabelingMembership.objects.create(
            labeling=self.labeling,
            user=self.owner,
            role=LabelingMembership.Role.OWNER,
        )

        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.url = reverse("import-items-csv", args=[self.labeling.id])

    def test_valid_csv_imports_items(self):
        upload = SimpleUploadedFile(
            "itens.csv",
            b"titulo,descricao\nTenis,Bom estado\nCamisa,Nova\n",
            content_type="text/csv",
        )

        response = self.client.put(self.url, {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Labeling.objects.filter(id=self.labeling.id).exists())
        self.assertEqual(Item.objects.filter(labeling=self.labeling).count(), 2)

        self.labeling.refresh_from_db()
        self.assertEqual(self.labeling.column_names, ["titulo", "descricao"])

    def test_unreadable_csv_deletes_the_labeling(self):
        # Unterminated quote: pandas raises while parsing.
        upload = SimpleUploadedFile(
            "quebrado.csv",
            b'titulo,descricao\n"Tenis,Bom estado\n',
            content_type="text/csv",
        )

        response = self.client.put(self.url, {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Labeling.objects.filter(id=self.labeling.id).exists())
        self.assertEqual(Item.objects.filter(labeling_id=self.labeling.id).count(), 0)

    def test_row_with_extra_column_deletes_the_labeling(self):
        # Parsing succeeds here: pandas turns the extra column into the index,
        # and the failure only shows up when the items are inserted.
        upload = SimpleUploadedFile(
            "coluna_a_mais.csv",
            b"titulo,descricao\nTenis,Bom estado,sobrando\n",
            content_type="text/csv",
        )

        response = self.client.put(self.url, {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Labeling.objects.filter(id=self.labeling.id).exists())
        self.assertEqual(Item.objects.filter(labeling_id=self.labeling.id).count(), 0)

    def test_non_csv_file_deletes_the_labeling(self):
        upload = SimpleUploadedFile(
            "planilha.txt",
            b"titulo,descricao\nTenis,Bom estado\n",
            content_type="text/plain",
        )

        response = self.client.put(self.url, {"file": upload}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Labeling.objects.filter(id=self.labeling.id).exists())


class AnnotatorCannotReadItemVoteCountsTest(TestCase):
    """P5: the item list carries vote counts (decision_payload): edit roles only."""

    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="p5i_owner", email="p5i_owner@example.com", password="x", account_type="admin")
        self.annotator = User.objects.create_user(username="p5i_ann", email="p5i_ann@example.com", password="x")
        self.outsider = User.objects.create_user(username="p5i_out", email="p5i_out@example.com", password="x")
        self.project = Project.objects.create(name="P5I", created_by=self.owner)
        self.labeling = Labeling.objects.create(
            project=self.project, title="P5I", created_by=self.owner,
            start_date=timezone.now().date(), final_date=timezone.now().date(),
        )
        LabelingMembership.objects.create(labeling=self.labeling, user=self.owner, role="owner")
        LabelingMembership.objects.create(labeling=self.labeling, user=self.annotator, role="annotator")
        Item.objects.create(labeling=self.labeling, payload={"a": 1}, row_index=0,
                            decision_payload={"votes": {"x": 2}})
        self.url = f"/labelings/{self.labeling.id}/items/"

    def _get(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c.get(self.url)

    def test_annotator_cannot_read_item_vote_counts(self):
        response = self._get(self.annotator)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn(b"decision_payload", response.content)

    def test_non_member_cannot_read_items(self):
        self.assertEqual(self._get(self.outsider).status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_and_admin_account_still_read_items(self):
        self.assertEqual(self._get(self.owner).status_code, status.HTTP_200_OK)
        admin = get_user_model().objects.create_user(username="p5i_adm", email="p5i_adm@example.com", password="x", account_type="admin")
        self.assertEqual(self._get(admin).status_code, status.HTTP_200_OK)


class NextLabelingRedirectTest(TestCase):
    """Study 1: a finished form_mode labeling points the annotator at the main labeling."""

    def setUp(self):
        from labeling.models import LabelingSection
        from answer.models import Answer
        self.Answer = Answer
        User = get_user_model()
        self.owner = User.objects.create_user(username="nl_owner", email="nl_owner@example.com", password="x")
        self.user = User.objects.create_user(username="nl_user", email="nl_user@example.com", password="x")
        self.project = Project.objects.create(name="NL", created_by=self.owner)
        self.main = self._labeling("Main", form_mode=False)
        self.part_a = self._labeling("Part A", form_mode=True, next_labeling=self.main)
        for lab in (self.main, self.part_a):
            LabelingSection.objects.create(labeling=lab, title="s", order=0, form_type=LabelingSection.FormType.MAIN)
            LabelingMembership.objects.create(labeling=lab, user=self.user, role="annotator")
        self.item = Item.objects.create(labeling=self.part_a, payload={}, row_index=0, status="pending")
        Item.objects.create(labeling=self.main, payload={"a": 1}, row_index=0, status="pending")

    def _labeling(self, title, **kw):
        return Labeling.objects.create(
            project=self.project, title=title, created_by=self.owner,
            start_date=timezone.now().date(), final_date=timezone.now().date(),
            status="active", **kw,
        )

    def _get(self, labeling=None):
        c = APIClient()
        c.force_authenticate(self.user)
        return c.get(f"/items/{(labeling or self.part_a).id}/")

    def _answer(self):
        self.Answer.objects.create(item=self.item, labeling=self.part_a, answered_by=self.user, answer_payload={})

    def test_next_labeling_returned_when_form_mode_done(self):
        self.assertEqual(self._get().status_code, 200)
        self._answer()
        r = self._get()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["code"], "NO_LABELINGS_TO_ANSWER")
        self.assertEqual(r.data["next_labeling_id"], self.main.id)

    def test_finished_form_mode_returns_next_labeling_on_revisit(self):
        from datetime import timedelta
        self._answer()
        self.Answer.objects.update(created_at=timezone.now() - timedelta(days=3))
        r = self._get()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["next_labeling_id"], self.main.id)

    def test_no_next_labeling_without_membership(self):
        self._answer()
        LabelingMembership.objects.filter(labeling=self.main, user=self.user).delete()
        r = self._get()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["code"], "NO_LABELINGS_TO_ANSWER")
        self.assertNotIn("next_labeling_id", r.data)

    def test_no_next_labeling_in_auto_mode(self):
        self.part_a.form_mode = False
        self.part_a.save()
        self.Answer.objects.create(item=self.item, labeling=self.part_a, answered_by=self.user, answer_payload={})
        self.item.status = "finished"
        self.item.save()
        r = self._get()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["code"], "NO_LABELINGS_TO_ANSWER")
        self.assertNotIn("next_labeling_id", r.data)
