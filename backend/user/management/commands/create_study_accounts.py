"""Study 1 account provisioning (study-specific, not for upstream).

Passwords go only to the 0600 output file; stdout carries counts only.
"""
import csv
import os
import secrets
import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from labeling.models import Labeling, LabelingMembership
from project.models import Project, ProjectMembership
from user.models import UserGroup, UserGroupMembership

GROUPS = ("legal", "technical", "export")
ANNOTATOR_GROUPS = ("legal", "technical")
OUT_FIELDS = ["email", "pseudonym", "user_id", "password"]


class Command(BaseCommand):
    help = "Create or update Study 1 annotator and export accounts."

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True, help="CSV: email,pseudonym,group")
        parser.add_argument("--project", required=True, type=int)
        parser.add_argument("--labelings", required=True, help="Comma-separated labeling ids")
        parser.add_argument("--out", help="Output CSV with new/reset passwords (required unless --existing-only)")
        parser.add_argument("--reset", action="store_true", help="Reset passwords of existing users")
        parser.add_argument(
            "--existing-only", action="store_true",
            help="Only update users that already exist (looked up by e-mail, e.g. invited): "
                 "set group and memberships; never touch passwords, write no --out file",
        )
        parser.add_argument("--overwrite", action="store_true", help="Delete an existing --out file first")

    def handle(self, *args, **opts):
        rows = self._read_rows(opts["input"])
        try:
            project = Project.objects.get(pk=opts["project"])
        except Project.DoesNotExist:
            raise CommandError(f"Unknown project {opts['project']}")
        try:
            lab_ids = [int(x) for x in opts["labelings"].split(",") if x.strip()]
        except ValueError:
            raise CommandError("--labelings must be comma-separated integers")
        if not lab_ids:
            raise CommandError("--labelings is empty")
        labelings = list(Labeling.objects.filter(pk__in=lab_ids, project=project))
        if {l.pk for l in labelings} != set(lab_ids):
            raise CommandError("Every labeling must exist and belong to --project")

        if opts["existing_only"]:
            if opts["out"] or opts["reset"]:
                raise CommandError("--existing-only cannot be combined with --out or --reset")
            User = get_user_model()
            missing = [
                r["email"] for r in rows if not User.objects.filter(email__iexact=r["email"]).exists()
            ]
            if missing:
                raise CommandError(f"{len(missing)} user(s) from the input do not exist; nothing changed")
            with transaction.atomic():
                counts = self._provision(rows, project, labelings, False, None)
            self.stdout.write("created={created} updated={updated} reset={reset}".format(**counts))
            return

        out_path = opts["out"]
        if not out_path:
            raise CommandError("--out is required unless --existing-only is given")
        if opts["overwrite"] and os.path.lexists(out_path):
            os.unlink(out_path)
        try:
            fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise CommandError(f"{out_path} exists; pass --overwrite to replace it")
        ok = False
        try:
            with os.fdopen(fd, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=OUT_FIELDS)
                writer.writeheader()
                with transaction.atomic():
                    counts = self._provision(rows, project, labelings, opts["reset"], writer)
            ok = True
        finally:
            if not ok:
                # No passwords may survive a rolled-back run.
                try:
                    os.unlink(out_path)
                except OSError:
                    pass
        self.stdout.write("created={created} updated={updated} reset={reset}".format(**counts))

    def _read_rows(self, path):
        try:
            with open(path, newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or not {"email", "pseudonym", "group"} <= set(reader.fieldnames):
                    raise CommandError("Input needs columns email,pseudonym,group")
                rows = [
                    {k: (r.get(k) or "").strip() for k in ("email", "pseudonym", "group")}
                    for r in reader
                ]
        except OSError as e:
            raise CommandError(f"Cannot read input: {e.strerror}")
        seen = set()
        for n, r in enumerate(rows, start=2):
            if not r["email"] or not r["pseudonym"]:
                raise CommandError(f"Line {n}: email and pseudonym are required")
            if r["group"] not in GROUPS:
                raise CommandError(f"Line {n}: unknown group {r['group']!r}; expected one of {GROUPS}")
            key = r["email"].lower()
            if key in seen:
                raise CommandError(f"Line {n}: duplicate email {r['email']}")
            seen.add(key)
        return rows

    def _provision(self, rows, project, labelings, reset, writer):
        User = get_user_model()
        counts = {"created": 0, "updated": 0, "reset": 0}
        groups = {
            name: UserGroup.objects.get_or_create(name=name)[0] for name in ANNOTATOR_GROUPS
        }
        for r in rows:
            is_export = r["group"] == "export"
            user = User.objects.filter(email__iexact=r["email"]).first()
            password = None
            if user is None:
                password = secrets.token_urlsafe(12)
                user = User.objects.create_user(
                    username=uuid.uuid4().hex, email=r["email"], password=password
                )
                counts["created"] += 1
            elif reset:
                password = secrets.token_urlsafe(12)
                user.set_password(password)
                counts["reset"] += 1
            else:
                counts["updated"] += 1
            user.first_name = r["pseudonym"]
            if is_export:
                user.account_type = User.AccountType.ADMIN
            user.save()

            ProjectMembership.objects.get_or_create(
                project=project, user=user,
                defaults={"role": ProjectMembership.RoleChoices.ANNOTATOR},
            )
            # Study groups are exclusive; the export account is in none.
            UserGroupMembership.objects.filter(
                user=user, group__name__in=ANNOTATOR_GROUPS
            ).exclude(group__name=r["group"]).delete()
            if not is_export:
                UserGroupMembership.objects.get_or_create(group=groups[r["group"]], user=user)

            role = LabelingMembership.Role.ADMIN if is_export else LabelingMembership.Role.ANNOTATOR
            for lab in labelings:
                lm, created = LabelingMembership.objects.get_or_create(
                    user=user, labeling=lab, defaults={"role": role}
                )
                if not created and lm.role != role:
                    lm.role = role
                    lm.save(update_fields=["role"])

            if password is not None:
                writer.writerow({
                    "email": user.email, "pseudonym": r["pseudonym"],
                    "user_id": user.pk, "password": password,
                })
        return counts
