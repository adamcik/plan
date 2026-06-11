# Modernization Handoff

Goal: remove YUI and `django-compressor`, move to HTML5 + Tailwind through VitePlus, and keep the app a plain server-rendered Django webapp with progressive enhancement.

The initial pass should be a port, not a redesign. Keep the app recognizable while replacing the 18+ year-old frontend foundation.

## Core Principles

- Django templates, routes, links, and forms remain the source of truth.
- The app must remain functional without JavaScript.
- JavaScript is progressive enhancement only.
- No client-side routing, hydration dependency, or JS-required forms.
- Strict CSP is non-negotiable.
- Target modern browsers from roughly the last 5 years.
- Drop IE hacks and XHTML-era compatibility code.
- Mobile is first-class, preferably mobile-first.
- Use small shippable stages.

## Timetable Constraint

Do not use Tailwind to implement the core timetable mechanics.

For `#schedule`, keep custom CSS responsible for:

- table layout
- column widths
- row heights
- borders and grid lines
- sticky time column
- overflow behavior
- lecture cell geometry
- `rowspan` / `colspan` behavior
- print behavior
- course color application, if that is simpler there

Tailwind may affect inherited site-level basics only, such as font family, base text rendering, and link defaults if compatible.

Do not convert timetable cells/rows into Tailwind utility soup. The timetable is the core product surface and should stay hand-authored, readable, and regression-testable.

## Color Identity

Preserve the course color identity. This is the soul of the app.

Colors must remain visually consistent across:

- schedule lecture cells
- course tables
- lecture tables
- any other intentionally color-coded course/lecture surfaces

The implementation is fluid. Acceptable approaches include:

- current template-injected `.course-{{ id }}` CSS
- inline styles
- CSS custom properties
- generated CSS palette maps
- static classes/data attrs, if still server-safe

Constraints:

- must work without JavaScript
- do not replace with Tailwind palette colors unless deliberately matching existing palette
- keep print and mobile behavior compatible
- keep ColorBrewer attribution if still using that palette

## Mobile Policy

Mobile is first-class.

- Build layouts mobile-first, then enhance upward with Tailwind breakpoints.
- Non-schedule UI should not require horizontal scrolling.
- Forms, action bars, course/lecture tables, tips, footer, and navigation should be comfortable on phone widths.
- Touch targets should be reasonably sized.
- Advanced options must be usable on mobile.
- Verify around 390px width and with constrained viewport height.
- Preserve no-JS functionality on mobile.

For the core schedule table:

- horizontal scrolling is acceptable because of intrinsic complexity
- scrolling must be deliberate and polished
- keep sticky time column only if reliable
- do not collapse the timetable into cards in the initial port unless explicitly chosen later

## Asset Architecture

Keep Django `staticfiles` as the collection/serving layer.

Use VitePlus as an asset pipeline only:

- compile Tailwind/CSS
- bundle small vanilla JS enhancement modules
- emit a manifest and hashed build output
- do not introduce SPA architecture

Use a manifest-backed template tag similar to `{% static %}`:

```django
{% load assets static %}

<link rel="icon" type="image/svg+xml" href="{% static 'favicon.svg' %}">
<link rel="stylesheet" href="{% asset 'styles/app.css' %}">
<script type="module" src="{% asset 'js/app.js' %}"></script>
```

Use `{% asset %}` for VitePlus-built CSS/JS. Use `{% static %}` for stable public files such as favicons.

## Proposed File Layout

```text
assets/
  styles/
    app.css
    schedule.css
    base.css
    components.css
    icons.css
  js/
    app.js
    autocomplete.js
    toggle.js
    advanced.js
    navigation.js
    calendar.js
  vendor/
    auto-complete.min.js
    auto-complete.css
    d3.v7.js
    plot.v0.6.js
    htl.v0.3.1.js
  dist/
    manifest.json
    assets/...
plan/
  static/
    favicon.svg
    favicon.png
plan/common/templatetags/
  assets.py
```

`assets/dist/` is generated and should be gitignored.

Prefer keeping source assets out of `plan/static/...`. `plan/static/...` should contain only stable public static files, if any.

## CSS Shape

Bundle schedule CSS into the main app CSS, but keep it as a separate source file.

Example:

```css
@import "tailwindcss";

@import "./base.css";
@import "./components.css";
@import "./icons.css";
@import "./schedule.css";
```

Keep `schedule.css` loaded after Tailwind/components so scoped `#schedule` rules win.

## Dev Workflow

Ideal long-term dev workflow: one managed command starts app, DB, and asset watcher.

Short term is flexible:

- `runserver` alone would be nice
- requiring a separate VitePlus `--watch` process is acceptable
- this repo already uses `run-db`, so multiple local processes are acceptable initially

Production/Nix/CI must build assets explicitly. Do not rely on generated assets being committed.

## Icons

Keep a single SVG sprite approach.

The exact generation location and asset pipeline integration are fluid, but avoid scattering icon implementations across the app.

## Vendor JavaScript

Keep tiny vendored dependencies under `assets/vendor/`.

The autocomplete library is already vendored; no need to npm-ify it unless useful.

## PDF / Print

PDF links may be kept, replaced with print CSS, or dropped after checking usage logs.

Print support for the schedule should remain a deliberate part of the custom timetable CSS if PDF is removed.

## Phased Plan

### 1. Asset Pipeline Stage

- Add VitePlus/Tailwind config.
- Add `assets/styles/app.css` and `assets/js/app.js` entrypoints.
- Configure build output to gitignored `assets/dist/`.
- Generate a Vite manifest.
- Add `assets/dist` to Django `STATICFILES_DIRS`.
- Add `{% asset %}` template tag that reads the manifest.
- In production/build mode, fail hard if manifest or asset key is missing.
- For dev, either require `vp build --watch` or support dev-server URLs when `DJANGO_DEBUG=true`.
- Keep current UI visually unchanged as much as possible.

### 2. Compressor Removal Stage

- Remove `django-compressor` from dependencies.
- Remove `compressor` from `INSTALLED_APPS`.
- Remove `compressor.finders.CompressorFinder`.
- Remove `COMPRESS_*` settings.
- Remove `{% load compress %}`.
- Replace `{% compress css/js %}` blocks with `{% asset %}` / `{% static %}` includes.
- Update Nix static checks/builds to run frontend build before `collectstatic`.
- Remove `python manage.py compress --force` from Nix/container static builds.
- Ensure strict CSP still passes.

### 3. Static Source Move Stage

Move source files:

- `plan/static/css/schedule.css` -> `assets/styles/schedule.css`
- useful parts of `plan/static/css/style.css` -> `assets/styles/base.css` / `components.css`
- `plan/static/css/icons.css` -> `assets/styles/icons.css`
- `plan/static/js/*.js` -> `assets/js/*.js`
- `plan/static/js/lib/*` -> `assets/vendor/*`

Delete after migration:

- `plan/static/css/reset.css`
- `plan/static/css/fonts.css`
- `plan/static/css/grids.css`
- `plan/static/css/base.css`
- old source JS/CSS files once bundled

Keep or move as public static:

- `favicon.svg`
- `favicon.png`

### 4. HTML5 Port Stage

- Convert `plan/templates/base.html` from XHTML 1.1 to HTML5.
- Remove XML declaration.
- Use `<!doctype html>`.
- Use `<html lang="en">`.
- Remove `xmlns` and `xml:lang`.
- Remove redundant `type="text/javascript"` and `type="text/css"`.
- Normalize boolean attributes like `checked`.
- Drop IE hacks.
- Do not redesign yet.

### 5. Tailwind/YUI Port Stage

Replace YUI layout usage in templates:

- `base_site.html`
- `start.html`
- `schedule.html`
- `schedule_table_footer.html`
- `courses.html`
- `lectures.html`
- `tips.html`

Remove reliance on:

- `.yui-g`
- `.yui-u`
- `.first`
- `#doc2`
- `.yui-t4`
- YUI grid body centering

Use Tailwind for non-schedule layout:

- page shell
- header/footer
- two-column layouts
- forms
- action rows
- tips
- course/lecture table wrappers and basic presentation

Port the current appearance first. Avoid a broad redesign in this stage.

Remove the Yahoo! UI Library attribution once YUI is gone.

### 6. Timetable Preservation Stage

- Keep `schedule_table.html` mostly unchanged.
- Keep custom timetable mechanics in `schedule.css` scoped under `#schedule`.
- Bundle `schedule.css` into `app.css`.
- Preserve current color identity.
- Verify desktop and mobile behavior before/after.

### 7. Progressive Enhancement JS Stage

Bundle current vanilla JS as enhancement modules:

- autocomplete
- advanced filter/toggle controls
- keyboard navigation
- calendar/about graph if applicable

Rules:

- all core flows work without JS
- no client-side routing
- no hydration dependency
- strict CSP compatibility
- prefer external module files over inline scripts

### 8. Cleanup Stage

- Delete YUI CSS files.
- Remove YUI attribution.
- Remove obsolete global CSS.
- Reassess PDF links after log check.
- Keep only useful public files in `plan/static/`.

## Verification Per Stage

Run:

- `nix fmt`
- `nix flake check`

Use Playwright smoke checks for:

- front page
- normal schedule view
- advanced schedule view
- mobile schedule around 390px width
- group selection
- about/statistics if JS-backed

Also verify:

- no-JS baseline for core flows
- mobile no-JS baseline
- CSP behavior
- manifest resolution
- `collectstatic` includes built assets
- container/static build includes built assets

## Key Risks

- Tailwind preflight may change table rendering. Keep timetable rules scoped and loaded after Tailwind.
- Course/lecture tables need colors preserved while layout is modernized.
- Manifest/static path handling must work inside Nix sandboxes.
- Dropping compressor drops current compressor-managed static minification and Brotli behavior. Handle precompressed assets separately only if actually needed.
- Mobile support should improve, not regress into merely desktop-compatible pages.
