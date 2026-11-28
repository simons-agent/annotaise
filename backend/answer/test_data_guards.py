"""Study 1: no manager action may silently destroy or orphan collected answers, and an
annotator invitation must assign the person somewhere (2026-11-27: an invited professor
saw no form, and project/labeling deletes cascaded to answers)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from answer.models import Answer, BackgroundAnswer
from item.models import Item
from labeling.models import Labeling, LabelingMembership, LabelingSection, LabelingElement
from project.models import Project, ProjectMembership

H = {"HTTP_HOST": "localhost"}


class StudyDataGuardsTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="g_owner", email="g_owner@example.com", password="x", account_type="admin")
        self.annotator = User.objects.create_user(username="g_ann", email="g_ann@example.com", password="x")
        self.project = Project.objects.create(name="Guard", created_by=self.owner)
        ProjectMembership.objects.create(project=self.project, user=self.owner, role="owner")
        self.labeling = Labeling.objects.create(project=self.project, title="Guard L", created_by=self.owner,
                                                start_date=timezone.now().date(), final_date=timezone.now().date())
        LabelingMembership.objects.create(labeling=self.labeling, user=self.owner, role="owner")
        LabelingMembership.objects.create(labeling=self.labeling, user=self.annotator, role="annotator")
        section = LabelingSection.objects.create(labeling=self.labeling, form_type=LabelingSection.FormType.MAIN, title="M", order=1)
        self.q = LabelingElement.objects.create(labeling_section=section, text="Q", question_type="text", order=1)
        self.item = Item.objects.create(labeling=self.labeling, payload={"r": 1}, row_index=0)

    def _as(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def _answer(self):
        Answer.objects.create(item=self.item, labeling=self.labeling, answered_by=self.annotator,
                              answer_payload={str(self.q.id): "x"})

    def test_labeling_with_answers_cannot_be_deleted(self):
        self._answer()
        r = self._as(self.owner).delete(f"/labelings/{self.labeling.id}/", **H)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.data["code"], "HAS_ANSWERS")
        self.assertTrue(Labeling.objects.filter(pk=self.labeling.pk).exists())

    def test_labeling_with_background_answers_cannot_be_deleted(self):
        BackgroundAnswer.objects.create(labeling=self.labeling, answered_by=self.annotator, answer_payload={"1": "x"})
        r = self._as(self.owner).delete(f"/labelings/{self.labeling.id}/", **H)
        self.assertEqual(r.status_code, 409, r.content)

    def test_empty_labeling_can_still_be_deleted(self):
        r = self._as(self.owner).delete(f"/labelings/{self.labeling.id}/", **H)
        self.assertEqual(r.status_code, 204, r.content)

    def test_project_with_answers_cannot_be_deleted(self):
        self._answer()
        r = self._as(self.owner).delete(f"/projects/{self.project.id}/", **H)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(Labeling.objects.get(pk=self.labeling.pk).project_id, self.project.id)

    def test_removing_the_last_project_owner_is_refused_not_deleting_the_project(self):
        m = ProjectMembership.objects.get(project=self.project, user=self.owner)
        r = self._as(self.owner).delete(f"/project-memberships/{m.id}/", **H)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.data["code"], "LAST_OWNER")
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

    def test_demoting_the_last_project_owner_is_refused(self):
        m = ProjectMembership.objects.get(project=self.project, user=self.owner)
        r = self._as(self.owner).patch(f"/project-memberships/{m.id}/", {"role": "viewer"}, format="json", **H)
        self.assertEqual(r.status_code, 409, r.content)

    def test_user_with_answers_cannot_be_deleted_by_an_admin_or_themselves(self):
        self._answer()
        r = self._as(self.owner).delete(f"/users/{self.annotator.id}/", **H)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.data["code"], "USER_HAS_ANSWERS")
        r = self._as(self.annotator).delete("/users/current/", **H)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertTrue(get_user_model().objects.filter(pk=self.annotator.pk).exists())
        self.assertEqual(Answer.objects.get().answered_by_id, self.annotator.id)

    def test_user_without_answers_can_still_be_deleted(self):
        r = self._as(self.owner).delete(f"/users/{self.annotator.id}/", **H)
        self.assertEqual(r.status_code, 204, r.content)

    def test_annotator_invitation_without_assignment_is_refused(self):
        r = self._as(self.owner).post("/invitations/", {"email": "new@example.com", "role": "standard"}, format="json", **H)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn("ASSIGNMENT_REQUIRED", str(r.data))
        self.assertFalse(get_user_model().objects.filter(email="new@example.com").exists())

    def test_annotator_invitation_with_project_assigns_its_labelings(self):
        r = self._as(self.owner).post("/invitations/", {"email": "new@example.com", "role": "standard",
                                                        "project_ids": [self.project.id]}, format="json", **H)
        self.assertEqual(r.status_code, 201, r.content)
        user = get_user_model().objects.get(email="new@example.com")
        self.assertTrue(LabelingMembership.objects.filter(user=user, labeling=self.labeling, role="annotator").exists())
        self.assertTrue(ProjectMembership.objects.filter(user=user, project=self.project).exists())

    def test_membership_list_honours_user_and_labeling_filters(self):
        r = self._as(self.owner).get(f"/labeling-memberships/?user={self.annotator.id}", **H)
        rows = r.data.get("results", r.data) if isinstance(r.data, dict) else r.data
        self.assertEqual({m["user"] for m in rows}, {self.annotator.id})


class FailedImportKeepsFormTest(TestCase):
    """A broken CSV uploaded to a form-mode labeling that still holds its placeholder record
    must not delete the labeling (and with it the form)."""

    def test_bad_upload_keeps_labeling_and_form(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        User = get_user_model()
        owner = User.objects.create_user(username="imp_owner", email="imp_owner@example.com", password="x", account_type="admin")
        project = Project.objects.create(name="Imp", created_by=owner)
        labeling = Labeling.objects.create(project=project, title="Imp", created_by=owner, form_mode=True,
                                           start_date=timezone.now().date(), final_date=timezone.now().date())
        LabelingMembership.objects.create(labeling=labeling, user=owner, role="owner")
        LabelingSection.objects.create(labeling=labeling, form_type=LabelingSection.FormType.MAIN, title="M", order=1)
        Item.objects.create(labeling=labeling, payload={}, row_index=0)
        c = APIClient()
        c.force_authenticate(owner)
        bad = SimpleUploadedFile("bad.txt", b"not a csv", content_type="text/plain")
        r = c.put(f"/labelings/{labeling.id}/import-items-csv/", {"file": bad}, format="multipart", **H)
        self.assertGreaterEqual(r.status_code, 400)
        self.assertTrue(Labeling.objects.filter(pk=labeling.pk).exists())
        self.assertEqual(LabelingSection.objects.filter(labeling=labeling).count(), 1)
