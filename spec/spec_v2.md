# safe-whale v2 - Notebook UI Specification

## Summary

`safe-whale` should move from the current single-screen pane layout to a notebook-style UI that separates discovery, profile management, launcher management, cleanup, and help into task-oriented surfaces.

The main product goals for v2 are:

1. Make package discovery feel much closer to PyPI search, without depending on a strong public relevance-search API.
1. Treat package **usage pattern** as first-class data so the UI can show the right actions for CLI, pipe-oriented, and TUI apps.
1. Let users choose a folder where `safe-whale` creates launch wrappers, making the app function like `pipx`, but backed by containers instead of isolated virtual environments.
1. Add a managed cleanup experience for Docker images, containers, and other artifacts created by `safe-whale`.
1. Provide pervasive help: a help panel for the current focus plus tooltips for individual controls.

This spec assumes the current codebase as of v1:

- a single `MainWindow` with catalog/config/output panes
- catalog entries with `interaction` but limited metadata
- JSON-based profile/history persistence
- no launcher directory, no managed cleanup view, and no inline help system

______________________________________________________________________

## Product principles

- **Action follows tool type.** The app should not pretend every package is runnable the same way.
- **Fast local UI, selective remote fetch.** Search and filtering must feel instant; network fetches enrich results, not gate the UI.
- **Only manage what safe-whale created.** Cleanup should replace `docker prune` for `safe-whale` assets, not become a general Docker Desktop clone.
- **No embedded terminal.** TUI apps and wrapper-first CLI flows should launch outside the main app.
- **Help is always nearby.** Every tab needs contextual explanation, not just a separate help menu.

______________________________________________________________________

## Terminology

### Usage patterns

Each catalog entry and saved profile should declare a `usage_pattern` that drives filtering, affordances, and default actions.

| Usage pattern | Meaning | Primary action in UI |
| --- | --- | --- |
| `single_run_cli` | Typical one-shot command that works well in the output panel | Build and run in app |
| `wrapper_cli` | Command is mainly useful from a shell or editor integration | Build/install wrapper |
| `pipe_filter` | Command is usually used in pipelines or redirected stdin/stdout | Build/install wrapper; optional file-based sample run |
| `tui_terminal` | Full-screen or terminal-native app requiring a real TTY | Build/install wrapper; open terminal |

`interaction` remains useful at runtime, but `usage_pattern` is the higher-level product concept used by the notebook UI.

### Managed assets

Artifacts created by `safe-whale` and eligible for cleanup:

- generated images and tags
- containers started by `safe-whale`
- generated launcher/wrapper files
- cached metadata and generated Dockerfiles

______________________________________________________________________

## Target notebook layout

The root window should become a `ttk.Notebook` with these tabs:

1. **Catalog**
   - search, filter, result list, metadata/details panel
   - package actions based on usage pattern
1. **Profiles**
   - saved profiles, profile categories, defaults, notes
   - quick actions: run, install wrapper, open terminal, edit
1. **Launchers**
   - wrapper directory selection
   - generated wrappers list, validation, PATH guidance
1. **Cleanup**
   - safe-whale-managed Docker images/containers/cache/launchers
   - selective delete and bulk cleanup
1. **Activity**
   - run history, build history, last errors, recent actions

A persistent **Help panel** should sit to the right of the notebook or as a collapsible lower pane:

- updates when focus changes
- shows "what this does", risks, and recommended workflow
- links to deeper docs where needed

Tooltips should exist for every actionable control and every security option.

______________________________________________________________________

## Functional requirements

## 1. Catalog

### 1.1 Search and discovery

The catalog must provide discovery that feels substantially richer than the current substring search.

Because PyPI does not expose a strong supported public relevance API, v2 should use a **hybrid catalog strategy**:

1. **Local searchable index**
   - bundled with the app or refreshed periodically
   - includes normalized package name, summary, keywords, classifiers, project URLs, usage pattern, tags, aliases, and curated boosts
   - supports exact match, prefix match, fuzzy name match, tag match, and classifier match
1. **On-demand exact metadata fetch**
   - use the package JSON API for known package names
   - enrich selected entries with full metadata and latest release details
1. **Curated safe-whale annotations**
   - manual or semi-manual tags for usage patterns
   - manual aliases for common user intent (`http`, `sql`, `terminal editor`, `download`, etc.)

The product should not promise PyPI-grade relevance across the full public index on day one. Instead it should deliver:

- fast search over a broad local index
- clear ranking rules
- filter chips for narrowing results quickly
- transparent messaging when a result is local-only vs freshly fetched

### 1.2 Metadata panel

Selecting a package should open a metadata/details panel that shows as much useful package information as possible, including:

- package name and normalized name
- summary / description excerpt
- latest version
- release date
- license
- author / maintainer when available
- project URLs (homepage, docs, source, issues)
- `requires-python`
- classifiers
- keywords/tags
- distribution files summary (wheel/sdist availability)
- safe-whale annotations:
  - usage pattern
  - default interaction mode
  - apt/system package hints
  - wrapper recommendation
  - network recommendation

The panel should also show the **recommended actions** for the selected package:

- Run in app
- Open in terminal
- Install/update wrapper
- Save profile

### 1.3 Catalog filters

The catalog must support rapid grouping and filtering by:

- usage pattern
- interaction type
- category/tag
- wrapper recommended / not recommended
- has system package requirements
- exact / fuzzy match mode

This is required so TUI, pipe-oriented, and wrapper-first tools stop looking like generic one-shot CLIs.

______________________________________________________________________

## 2. Profiles

Profiles should evolve from "saved run config" into "saved usage recipe".

Each profile should store:

- display name
- package spec and entrypoint
- usage pattern
- interaction mode
- security settings
- notes
- launcher preference
- optional tags/category labels

Profile categories should primarily reflect usage patterns, with optional user tags on top.

Examples:

- `CLI tools`
- `Pipe filters`
- `TUI terminal apps`
- user tags like `api`, `downloads`, `formatting`, `database`

The Profiles tab should support:

- filter by category/tag
- show the right actions per profile
- detect stale wrappers after profile changes
- duplicate/edit/export/delete profile

Behavior rules:

- `single_run_cli`: default action is **Run in app**
- `wrapper_cli`: default action is **Install wrapper**
- `pipe_filter`: default action is **Install wrapper**
- `tui_terminal`: default action is **Open in terminal** or **Install wrapper**

______________________________________________________________________

## 3. Launch wrappers

### 3.1 Wrapper directory

The app must let the user choose a folder for generated launch wrappers. This is an app-level setting, not a per-profile setting.

Requirements:

- first-run prompt or clear empty-state prompt
- browse/select folder from the Launchers tab
- validate writability
- show whether the folder appears to be on `PATH`
- preserve the choice in app settings

### 3.2 Wrapper behavior

Wrapper generation should make `safe-whale` act like `pipx` for command launching, except execution happens through a container image built and managed by `safe-whale`.

Wrapper responsibilities:

- call the correct container engine
- reference the managed image or trigger a build/update flow when needed
- forward CLI arguments transparently
- preserve exit codes
- use terminal launching for TUI profiles
- avoid pretending the GUI hosts a terminal

Platform expectations:

- Windows: `.cmd` first; optional PowerShell companion if useful
- POSIX: executable shell script

The Launchers tab should show:

- wrapper name
- target profile/package
- usage pattern
- install path
- last updated timestamp
- status (`ok`, `missing target`, `needs rebuild`, `wrapper dir unavailable`)

### 3.3 Wrapper-first actions

For `wrapper_cli`, `pipe_filter`, and `tui_terminal`, the catalog and profiles tabs should emphasize wrapper installation over in-app execution.

For `pipe_filter`, the GUI may still support a file-based sample run, but that is secondary to wrapper installation.

______________________________________________________________________

## 4. Cleanup

The Cleanup tab should replace ad hoc `docker prune` usage for assets created by `safe-whale`.

Scope:

- only images, containers, build contexts, Dockerfiles, wrapper files, and caches that `safe-whale` created or explicitly tracks
- no attempt to manage unrelated Docker workloads

The cleanup view should group assets by:

- images
- stopped containers
- running containers started by `safe-whale`
- generated Dockerfiles/cache
- wrappers

Each row should show:

- name / id
- source profile or package
- created time
- last used time when known
- size estimate when available
- safe-to-delete status

Actions:

- delete one item
- delete selected items
- clean all unused safe-whale assets
- rebuild wrapper target after cleanup when necessary

This requires persistent tracking of asset provenance rather than inferring ownership only from current Docker state.

______________________________________________________________________

## 5. Help system

Help must be pervasive rather than hidden behind menus.

Requirements:

- every major tab has a contextual help article
- every important control has a tooltip
- focus changes update the help panel
- risky settings explain tradeoffs in plain language
- usage-pattern help explains why some tools open in a terminal or prefer wrappers

Minimum help topics:

- catalog search behavior and result ranking
- usage patterns
- wrappers and PATH setup
- security options
- cleanup scope and safety
- why TUI apps cannot run in the output panel

______________________________________________________________________

## Data model changes

The current models are too small for v2. Add or expand the following concepts.

### `CatalogEntry`

Add:

- `usage_pattern`
- `tags: list[str]`
- `aliases: list[str]`
- `classifiers: list[str]`
- `keywords: list[str]`
- `project_urls: dict[str, str]`
- `latest_version`
- `release_date`
- `requires_python`
- `license`
- `wrapper_recommended: bool`
- `metadata_status` (`bundled`, `cached`, `fetched`, `stale`)

### `Profile`

Add:

- `usage_pattern`
- `tags`
- `launcher_name`
- `launcher_installed`
- `launcher_updated_at`
- `preferred_action`

### New settings model

Add an app settings record:

- `wrapper_dir`
- `help_panel_visible`
- `catalog_cache_ttl`
- `last_selected_tab`
- `preferred_search_mode`

### New managed-asset model

Track:

- asset type
- engine
- image tag / container id / wrapper path
- source profile/package
- created at / last used at
- state
- cleanup eligibility

______________________________________________________________________

## Storage and architecture implications

The current JSON files are workable for v1 but become fragile for v2. The recommended direction is:

- keep `storage.py` as the facade
- migrate underlying persistence to SQLite

Why:

- better fit for searchable catalog cache
- better fit for managed asset inventory
- easier cleanup queries
- easier history/activity filtering

Suggested module additions:

- `safe_whale\settings.py`
- `safe_whale\metadata.py`
- `safe_whale\launchers.py`
- `safe_whale\cleanup.py`
- `safe_whale\help.py`
- `safe_whale\ui\notebook_window.py` or split panels under `safe_whale\ui\`

Suggested UI breakdown:

- `catalog_tab.py`
- `profiles_tab.py`
- `launchers_tab.py`
- `cleanup_tab.py`
- `activity_tab.py`
- `help_panel.py`
- `tooltips.py`

______________________________________________________________________

## Delivery phases

## Phase 1 - Notebook shell and help foundation

### Goal

Replace the single-pane UI with a notebook shell and establish the contextual help system.

### Scope

- create notebook tabs
- move existing catalog/config/output/history behavior into tabbed layout
- add persistent help panel
- add tooltip infrastructure
- add app settings storage for selected tab and help visibility

### Outcome

The app feels structurally ready for v2 even before the richer catalog and cleanup logic lands.

### Acceptance criteria

- users can move between Catalog, Profiles, Launchers, Cleanup, and Activity tabs
- focus changes update the help panel content
- existing run/build/history workflows still work
- no feature regression for current catalog/profile behavior

______________________________________________________________________

## Phase 2 - Catalog v2 and metadata panel

### Goal

Make discovery, grouping, and metadata inspection strong enough to support a much larger package catalog.

### Scope

- add `usage_pattern` and tagging to catalog data
- implement local indexed search and ranking
- add result filters/chips
- add metadata panel with PyPI enrichment and caching
- add recommended-action logic per package

### Outcome

Users can find tools by intent and understand what kind of package they selected before they run or install anything.

### Acceptance criteria

- searches are instant against the local index
- selected entries show rich metadata
- catalog can filter rapidly by usage pattern
- TUI and wrapper-first tools no longer surface a misleading Run-in-app primary action

______________________________________________________________________

## Phase 3 - Profiles and launcher workflows

### Goal

Turn saved profiles into durable usage recipes and add pipx-like launcher installation.

### Scope

- expand profile model with usage pattern, tags, preferred action, and launcher status
- add Launchers tab
- add wrapper directory selection and validation
- generate platform-appropriate wrappers
- add PATH guidance and wrapper health states
- reframe default actions by usage pattern

### Outcome

`safe-whale` becomes useful for day-to-day command launching, not just one-off GUI runs.

### Acceptance criteria

- user can choose a wrapper directory
- wrapper-capable profiles can install/update wrappers
- wrapper list shows health/status clearly
- TUI/pipe/wrapper-first profiles direct users to the right action

______________________________________________________________________

## Phase 4 - Managed cleanup

### Goal

Give users visibility and control over every Docker-side artifact `safe-whale` created.

### Scope

- persist managed-asset inventory
- detect images/containers/wrappers/cache owned by `safe-whale`
- add Cleanup tab with filtering and bulk actions
- tie cleanup state back to profiles and wrappers

### Outcome

Users can reclaim disk space and clear stale assets without leaving the app or risking unrelated Docker workloads.

### Acceptance criteria

- cleanup only targets tracked `safe-whale` assets
- users can remove one, many, or all unused assets
- wrapper/profile states update after cleanup
- activity/history reflects cleanup actions

______________________________________________________________________

## Phase 5 - Polish, guidance, and quality

### Goal

Make the notebook UI understandable, resilient, and pleasant enough for broader use.

### Scope

- improve copy, empty states, and inline explanations
- add keyboard navigation across tabs and lists
- refine help content and tooltips
- add migration for existing profiles/history/settings
- performance tuning for larger local catalog indexes

### Outcome

The v2 workflow is coherent for both first-time users and repeat users managing many tools.

### Acceptance criteria

- major empty/error states explain next steps
- existing users are migrated without losing profiles/history
- catalog/search/help remain responsive with a substantially larger dataset

______________________________________________________________________

## Non-goals for v2

- embedded terminal emulation inside the Tkinter app
- managing Docker assets not created by `safe-whale`
- guaranteeing parity with all private or undocumented PyPI search behavior
- supporting ecosystems beyond PyPI in the same release

______________________________________________________________________

## Open design questions

1. How large should the bundled local package index be at first ship: curated top packages only, or a broader generated snapshot?
1. Should wrapper execution ever trigger implicit builds, or should wrappers only target already-built images?
1. For pipe-oriented tools, should the GUI support only file-based sample input, or a lightweight text input area too?
1. Should Activity stay a separate tab, or should run/build history live inside Profiles and Cleanup where context is closer?

______________________________________________________________________

## Recommended implementation order

Implement in this order:

1. Phase 1, because every later feature depends on the notebook shell and help plumbing.
1. Phase 2, because usage-pattern-aware catalog data drives the rest of the UX.
1. Phase 3, because wrappers are the core behavior shift for CLI, pipe, and TUI apps.
1. Phase 4, because cleanup depends on tracked assets introduced by wrapper/build workflows.
1. Phase 5, once the core flows are in place.
