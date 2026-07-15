# Plan, a timetable generator for NTNU students

This piece of software started out as a simple tool to assist in creating
readable timetables for NTNU courses. The earliest version of the site provided
this functionality and nothing more. As more fellow students started using the
software new features where added based on personal needs and suggestions from
other students.

## Today the software provides the following:

- Simple interface for adding courses.
- Customizable view of your timetable.
- Easy export to Google-Calendar via iCal.
- PDF-version for printing.
- User defined deadlines.
- Import of course data from ntnu.no or database-dumps.

## Required packages

- python3-django
- python3-django-compressor
- python3-lxml
- python3-psycopg2
- python3-pylibmc
- python3-reportlab
- python3-requests
- python3-sentry-sdk
- python3-sphinx
- python3-tqdm
- python3-vobject

## Request modifiers and middleware behavior

The app supports a few request modifiers that affect caching, conditional
responses, language selection, and debug rendering.

- `?no-cache`
  - Bypasses internal response cache reads in views that call
    `plan.common.utils.should_bypass_cache`.
  - Currently applies to schedule HTML and iCal views.
- `Cache-Control: no-cache`
  - Same bypass behavior as `?no-cache` for views using
    `should_bypass_cache`.
- `Pragma: no-cache`
  - Same bypass behavior as `?no-cache` for views using
    `should_bypass_cache`.
- `?no-modified-since`
  - Disables `If-Modified-Since`/`Last-Modified` short-circuiting in
    `check_modified_since`.
  - Does not disable ETag/`If-None-Match` handling.
- `?debug`
  - Only active when `DEBUG=True`.
  - Enables `text_debug_middleware`, which converts non-HTML responses to
    debug-friendly HTML output.

### Notes on `no-cache`

- `no-cache` is a **response-cache bypass**, not a full data-cache bypass.
- It bypasses rendered response/view caches (for example schedule HTML and iCal
  response cache lookups).
- It does **not** automatically bypass lower-level caches such as
  schedule/data/DB-derived caches unless a specific code path forwards a
  separate bypass flag.
- Conditional `304 Not Modified` responses may still be returned first if
  ETag/conditional headers match.

### Language query behavior

- Locale middleware currently interprets the raw query string as the language
  code (for example `?nb`), not key/value pairs like `?lang=nb`.

## Local dev: runserver

Use unified settings for runserver. `nix develop` sets local data, cache, and Postgres socket paths:

- `DJANGO_SETTINGS_MODULE=plan.settings`
- `DJANGO_DEBUG=true`
- `DJANGO_DEBUG_TOOLBAR=1` to enable Django Debug Toolbar
- `PLAN_BASE_DIR=...` to change the default `data/` directory

Offline mode prep (once after static/template changes):

```bash
./manage.py collectstatic --noinput
DJANGO_COMPRESS_ENABLED=true DJANGO_COMPRESS_OFFLINE=true ./manage.py compress --force
```

Runserver against helper DB:

```bash
nix develop
run-db
```

In another shell:

```bash
nix develop
./manage.py migrate
./manage.py runserver
```

## Container smoke test against helper DB

Use the helper in the dev shell. It loads the Nix image, uses host networking,
runs as your current user, and connects to the `run-db` Unix socket in
`data/pgdata`. It uses `data/cache` for Django file cache.

```bash
nix develop
run-db
```

In another shell:

```bash
nix develop
run-container
```

Use Podman instead of Docker:

```bash
run-container --podman
```

## Releases

Create all releases in GitHub. For patch releases, use GitHub's generated
notes; write the notes for minor and major releases by hand. A published stable
release publishes its version tag and advances `:latest`.

Run the **Publish development container** workflow from `main` to publish the
current development image and advance `:main`, without changing `:latest`.

Hatch's version is retained in the image metadata. Its `+` separator is changed
to `-` in the immutable image tag because OCI tags do not permit `+`.
