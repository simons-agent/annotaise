# Baseline (stock, commit 50b4a83)

Run from the repo root with a git-ignored local `.env` holding throwaway dev
values (DB name/user/password, superuser, dummy SMTP, `DJANGO_DB_HOST_PORT=55432`
to avoid a host port clash). Never committed.

Command:

    docker compose run --rm api uv run manage.py test

The command in the task brief (`... api python manage.py test`) fails with
`ModuleNotFoundError: No module named 'django'` because dependencies live in the
uv-managed `.venv`; `uv run` is required.

Result: `Ran 143 tests in 546.9s` -- `OK` (143 pass, 0 fail, 0 errors).
The full suite is slow (about 9 minutes).
