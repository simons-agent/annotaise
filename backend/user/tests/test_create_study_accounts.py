import csv
import os
import stat
import tempfile
from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient

from item.models import Item
from labeling.models import Labeling, LabelingElement, LabelingMembership, LabelingSection
from project.models import Project, ProjectMembership
from user.models import UserGroup, UserGroupMembership

User = get_user_model()

ROWS = [
    ("legal1@example.com", "L1", "legal"),
    ("tech1@example.com", "T1", "technical"),
]


class StudyAccountsBase(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="x"
        )
        self.project = Project.objects.create(name="Study", created_by=self.owner)
        self.lab_a = self._labeling("Form A")
        self.lab_b = self._labeling("Form B")
        self.out = os.path.join(self.tmp.name, "passwords.csv")

    def _labeling(self, title):
        return Labeling.objects.create(
            title=title, created_by=self.owner, project=self.project,
            start_date=date.today(), final_date=date.today(),
        )

    def write_input(self, rows=ROWS, name="accounts.csv"):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["email", "pseudonym", "group"])
            w.writerows(rows)
        return path

    def run_cmd(self, rows=ROWS, labelings=None, **opts):
        labelings = labelings or [self.lab_a.id, self.lab_b.id]
        stdout = StringIO()
        call_command(
            "create_study_accounts",
            input=self.write_input(rows),
            project=self.project.id,
            labelings=",".join(str(i) for i in labelings),
            out=self.out,
            stdout=stdout,
            **opts,
        )
        return stdout.getvalue()

    def read_out(self):
        with open(self.out, newline="") as f:
            return list(csv.DictReader(f))


class CreateStudyAccountsTests(StudyAccountsBase):
    def test_creates_users_in_groups_with_labeling_memberships(self):
        out = self.run_cmd()
        self.assertEqual(out.strip(), "created=2 updated=0 reset=0")
        for email, pseudonym, group in ROWS:
            u = User.objects.get(email=email)
            self.assertEqual(u.first_name, pseudonym)
            self.assertEqual(u.account_type, "standard")
            self.assertTrue(ProjectMembership.objects.filter(project=self.project, user=u).exists())
            self.assertEqual(
                list(UserGroupMembership.objects.filter(user=u).values_list("group__name", flat=True)),
                [group],
            )
            for lab in (self.lab_a, self.lab_b):
                self.assertEqual(
                    LabelingMembership.objects.get(user=u, labeling=lab).role, "annotator"
                )
        rows = self.read_out()
        self.assertEqual([r["email"] for r in rows], [r[0] for r in ROWS])
        self.assertEqual(list(rows[0].keys()), ["email", "pseudonym", "user_id", "password"])
        self.assertEqual(int(rows[0]["user_id"]), User.objects.get(email=ROWS[0][0]).id)
        self.assertTrue(rows[0]["password"])

    def test_export_account_is_admin_with_labeling_admin_role(self):
        self.run_cmd(rows=[("export@example.com", "privdev-export", "export")])
        u = User.objects.get(email="export@example.com")
        self.assertEqual(u.account_type, "admin")
        self.assertFalse(UserGroupMembership.objects.filter(user=u).exists())
        for lab in (self.lab_a, self.lab_b):
            self.assertEqual(LabelingMembership.objects.get(user=u, labeling=lab).role, "admin")

    def test_idempotent_keeps_password(self):
        self.run_cmd()
        hashes = {u.email: u.password for u in User.objects.filter(email__in=[r[0] for r in ROWS])}
        out = self.run_cmd(**{"overwrite": True})
        self.assertEqual(out.strip(), "created=0 updated=2 reset=0")
        for u in User.objects.filter(email__in=hashes):
            self.assertEqual(u.password, hashes[u.email])
        self.assertEqual(self.read_out(), [])
        self.assertEqual(LabelingMembership.objects.filter(role="annotator").count(), 4)
        self.assertEqual(UserGroupMembership.objects.count(), 2)

    def test_adding_labeling_later_is_idempotent(self):
        self.run_cmd(labelings=[self.lab_a.id])
        u = User.objects.get(email=ROWS[0][0])
        self.assertFalse(LabelingMembership.objects.filter(user=u, labeling=self.lab_b).exists())
        out = self.run_cmd(overwrite=True)
        self.assertEqual(out.strip(), "created=0 updated=2 reset=0")
        self.assertTrue(LabelingMembership.objects.filter(user=u, labeling=self.lab_b).exists())

    def test_reset_changes_password(self):
        self.run_cmd()
        old = User.objects.get(email=ROWS[0][0]).password
        out = self.run_cmd(reset=True, overwrite=True)
        self.assertEqual(out.strip(), "created=0 updated=0 reset=2")
        self.assertNotEqual(User.objects.get(email=ROWS[0][0]).password, old)
        rows = self.read_out()
        self.assertEqual(len(rows), 2)
        u = User.objects.get(email=ROWS[0][0])
        self.assertTrue(u.check_password(rows[0]["password"]))

    def test_out_file_mode_0600(self):
        old = os.umask(0)  # hostile umask must not widen the mode
        try:
            self.run_cmd()
        finally:
            os.umask(old)
        self.assertEqual(stat.S_IMODE(os.stat(self.out).st_mode), 0o600)

    def test_existing_permissive_file_refused(self):
        with open(self.out, "w") as f:
            f.write("keep")
        os.chmod(self.out, 0o644)
        with self.assertRaises(CommandError):
            self.run_cmd()
        with open(self.out) as f:
            self.assertEqual(f.read(), "keep")
        self.assertEqual(stat.S_IMODE(os.stat(self.out).st_mode), 0o644)
        self.assertEqual(User.objects.filter(email=ROWS[0][0]).count(), 0)

    def test_overwrite_recreates_0600(self):
        with open(self.out, "w") as f:
            f.write("old")
        os.chmod(self.out, 0o644)
        self.run_cmd(overwrite=True)
        self.assertEqual(stat.S_IMODE(os.stat(self.out).st_mode), 0o600)
        self.assertEqual(len(self.read_out()), 2)

    def test_stdout_has_no_password(self):
        out = self.run_cmd()
        for row in self.read_out():
            self.assertNotIn(row["password"], out)
        self.assertEqual(out.strip(), "created=2 updated=0 reset=0")

    def test_rejects_unknown_group(self):
        with self.assertRaises(CommandError):
            self.run_cmd(rows=[("x@example.com", "X", "medical")])
        self.assertFalse(User.objects.filter(email="x@example.com").exists())
        self.assertFalse(os.path.exists(self.out))

    def test_annotator_can_fetch_item_export_account_can_export(self):
        section = LabelingSection.objects.create(
            labeling=self.lab_a, form_type=LabelingSection.FormType.MAIN, title="Main", order=1
        )
        LabelingElement.objects.create(
            labeling_section=section, text="Q", order=1,
            question_type=LabelingElement.QuestionType.TEXT,
        )
        Item.objects.create(labeling=self.lab_a, payload={"t": "x"}, row_index=1)
        rows = ROWS[:1] + [("export@example.com", "privdev-export", "export")]
        self.run_cmd(rows=rows)
        pw = {r["email"]: r["password"] for r in self.read_out()}

        def client_for(email):
            c = APIClient()
            r = c.post("/api/auth/token/", {"email": email, "password": pw[email]}, format="json")
            self.assertEqual(r.status_code, 200, r.content)
            c.credentials(HTTP_AUTHORIZATION="Bearer " + r.json()["access"])
            return c

        ann = client_for(ROWS[0][0])
        self.assertEqual(ann.get(f"/items/{self.lab_a.id}/").status_code, 200)
        self.assertEqual(
            ann.get(f"/labelings/{self.lab_a.id}/answers/export/").status_code, 403
        )
        exp = client_for("export@example.com")
        self.assertEqual(exp.get(f"/labelings/{self.lab_a.id}/answers/export/").status_code, 200)
        self.assertEqual(
            exp.get(f"/labelings/{self.lab_a.id}/background-answers/").status_code, 200
        )
