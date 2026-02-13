# Technical Execution Plan: Authentication Flow & Submissions Table View

> **Status: COMPLETED** — All 6 phases implemented and committed.

## Context

The African Bamboo Dashboard frontend is a Next.js 15 App Router application with React 19, Tailwind CSS v4, and shadcn/ui. The backend provides a complete API: KoboToolbox-based JWT authentication (`POST /api/v1/auth/login`), user profile (`GET /api/v1/users/me`), paginated submissions (`GET /api/v1/odk/submissions/`), and form management with sync (`POST /api/v1/odk/forms/{id}/sync/`).

**Design references:**
- `docs/assets/dashboard-and-submissions-table-view/main page.jpg`
- `docs/assets/dashboard-and-submissions-table-view/Sidebar navigation.png`
- `docs/assets/dashboard-and-submissions-table-view/african-bamboo-logo-inverse.svg`

---

## Phase 1: Foundation — shadcn/ui Setup & Theming ✅

**Commit:** `b743ba6`

### What was done

1. Initialized shadcn/ui via `npx shadcn@latest init` (JS, App Router, `src/` directory, `@/` alias)
2. Installed components: button, input, label, card, badge, tabs, table, dropdown-menu, select, separator, skeleton, tooltip, avatar, sheet
3. Configured Tailwind CSS v4 theming in `globals.css` with CSS variables (HSL format) and `@theme inline` block
4. Copied logo SVG to `frontend/public/logo.svg` with `fill:currentColor` for flexible theming

### Key theming decisions
- **Primary:** Gold/yellow (`45 93% 47%` / `#EAB308`) for action buttons
- **Sidebar:** Dark background (`0 0% 10%` / `#1a1a1a`) with white text
- **Status badges:** Green (approved), yellow (on hold), red (rejected)

### Files created/modified
- `frontend/components.json`
- `frontend/src/lib/utils.js` — `cn()` utility
- `frontend/src/components/ui/*.jsx` — 14 shadcn components
- `frontend/src/app/globals.css` — Tailwind v4 theming
- `frontend/public/logo.svg`

---

## Phase 2: Auth Infrastructure ✅

**Commit:** `d0c2405`, `12d7811` (redirect loop fix)

### What was done

1. **Session management** (`src/lib/session.js`) — jose `SignJWT`/`jwtVerify` for stateless encrypted httpOnly cookies (12h expiry). Single file with both crypto and cookie functions (no `server-only` guard — required for Edge runtime middleware compatibility).

2. **Server Actions** (`src/app/actions/auth.js`) — `login()` and `logout()` functions. Login calls backend via `process.env.WEBDOMAIN` (full URL, e.g. `http://localhost:3000`), creates session cookie, redirects to `/dashboard`.

3. **Data Access Layer** (`src/lib/dal.js`) — `verifySession()` using React `cache` for deduplication. Server-only, redirects to `/login` if session invalid.

4. **Middleware** (`src/middleware.js`) — Edge-compatible route protection. Imports `decrypt` directly from `session.js`. Protects `/dashboard` routes, redirects authenticated users away from `/login`.

5. **API client** (`src/lib/api.js`) — Axios instance with `setApiToken()` and 401 interceptor.

6. **Auth context** (`src/context/AuthContext.js`) — Sets axios token **synchronously during render** (via `useRef` pattern) to prevent race condition where child hooks fire API calls before token is configured.

7. **Custom hooks:**
   - `src/hooks/useForms.js` — Context-based `FormsProvider` with shared `activeForm` state, `registerForm`, `syncForm`
   - `src/hooks/useSubmissions.js` — Submissions data fetching with pagination

### Key deviations from original plan
- **No `server-only` in session.js** — Caused silent failure in Edge runtime middleware, leading to redirect loops. Removed to keep single file.
- **No separate `session-crypto.js`** — Initially split for Edge compatibility, later merged back since removing `server-only` solved the issue.
- **`WEBDOMAIN` env var** — Used existing `WEBDOMAIN` from docker-compose instead of creating `BACKEND_URL`. Contains full URL (e.g. `http://localhost:3000`).
- **Synchronous token setting** — AuthContext sets axios token during render (not in `useEffect`) to prevent race condition with child hooks.
- **`useForms` is context-based** — Originally a plain hook, converted to `FormsProvider` context so `activeForm` state is shared across dashboard page and filter bar.

### Environment variables
```bash
WEBDOMAIN=http://localhost:3000    # Full URL, used by server actions
SESSION_SECRET=<openssl rand -base64 32>
```

### Files created
- `frontend/src/lib/session.js`
- `frontend/src/lib/dal.js`
- `frontend/src/lib/api.js`
- `frontend/src/app/actions/auth.js`
- `frontend/src/middleware.js`
- `frontend/src/context/AuthContext.js`
- `frontend/src/hooks/useForms.js`
- `frontend/src/hooks/useSubmissions.js`

---

## Phase 3: Login Page ✅

**Commit:** `2418637`

### What was done

1. **Login page** (`src/app/login/page.js`) — Server component with centered Card layout and `<Logo>` component
2. **Login form** (`src/app/login/login-form.js`) — Client component using React 19 `useActionState` with `login` Server Action

### Login form features
- KoboToolbox Server URL (pre-filled with `https://kf.kobotoolbox.org`)
- Username and Password fields
- Password show/hide toggle with `aria-label`
- Error display with `role="alert"` and `aria-live="polite"`
- Loading spinner via `pending` state from `useActionState`
- Native `<form action={action}>` — no `onSubmit`/`preventDefault`

### Key deviation
- **Inline SVG Logo component** (`src/components/logo.js`) — Uses `currentColor` fill so logo inherits text color from parent CSS. `<Image>` tag can't pass CSS color to SVG fills, so an inline SVG component was created instead.

### Files created
- `frontend/src/app/login/page.js`
- `frontend/src/app/login/login-form.js`
- `frontend/src/components/logo.js`

---

## Phase 4: Dashboard Layout — Sidebar & Shell ✅

**Commit:** `4bd34de`

### What was done

1. **Dashboard layout** (`src/app/dashboard/layout.js`) — Server component that calls `verifySession()`, wraps children in `AuthProvider` and `FormsProvider`
2. **Sidebar** (`src/components/app-sidebar.js`) — Collapsible dark sidebar with two states

### Sidebar navigation
| Item | Icon | Route |
|------|------|-------|
| Dashboard | BarChart3 | `/dashboard` |
| Map | Map | `/dashboard/map` |
| Forms | FileText | `/dashboard/forms` |
| Support | LifeBuoy | `/dashboard/support` (expanded only) |
| Settings | Settings | `/dashboard/settings` |

### Responsive behavior
| Breakpoint | Behavior |
|------------|----------|
| **Mobile (<768px)** | Sidebar hidden, hamburger → Sheet drawer from left |
| **Desktop (>=768px)** | Sidebar visible, toggle between expanded (w-60) and collapsed (w-16) |

### Key deviations
- **No separate `sidebar-nav-item.js`** — Nav item logic inlined in `app-sidebar.js` as `NavItem` function component
- **"Forms" instead of "Farmers and Enumerators"** — Nav item changed to link to `/dashboard/forms` with FileText icon
- **`FormsProvider` in layout** — Wraps all dashboard children so `useForms()` shares state

### Files created
- `frontend/src/app/dashboard/layout.js`
- `frontend/src/components/app-sidebar.js`

---

## Phase 5: Dashboard Content ✅

**Commit:** `c54e17a`, `e483663` (forms page + context refactor)

### What was done

1. **Dashboard page** (`src/app/dashboard/page.js`) — Client component with stats, filters, table, and pagination. Uses `activeForm` from shared `useForms()` context.

2. **Forms page** (`src/app/dashboard/forms/page.js`) — Register new forms + table listing with sync button per row.

3. **Settings page** (`src/app/dashboard/settings/page.js`) — Profile display (read-only) + logout button.

### Dashboard page structure
```
DashboardPage (client component)
├── DashboardHeader (title + Add data button)
├── StatsCardsRow (4 stat cards)
├── FilterBar (form dropdown + date range + reset)
├── FormSectionHeader (active form name + data count badge + export button)
├── TableControls (status tabs + search input)
├── SubmissionsTable (data rows with status badges)
└── TablePagination (previous/next + page indicator)
```

### Forms page structure
```
FormsPage
├── Register Form Card (asset UID + form name inputs + register button)
├── Status alert (success/error feedback)
└── Registered Forms Table
    ├── Columns: Name, Asset UID, Submissions, Last Synced, Actions
    └── Sync button per row (triggers POST /forms/{id}/sync/)
```

### Filter bar
- Form dropdown — controlled by `activeForm` / `setActiveForm` from `useForms()` context
- Date range selector (Last 7/30/90 days)
- Date display
- Reset button

### Components created
- `frontend/src/components/stat-card.js`
- `frontend/src/components/status-badge.js` (approved/on_hold/rejected)
- `frontend/src/components/table-pagination.js`
- `frontend/src/components/filter-bar.js`
- `frontend/src/components/dashboard-header.js`
- `frontend/src/components/submissions-table.js`
- `frontend/src/app/dashboard/forms/page.js`
- `frontend/src/app/dashboard/settings/page.js`
- `frontend/src/app/dashboard/support/page.js`

### Key deviations
- **No separate `dashboard-content.js`** — Content merged directly into `page.js` as a client component
- **Forms management page** — Added `/dashboard/forms` with register + sync (not in original plan)
- **Settings page** — Profile display + logout (not in original plan)
- **`useForms` as context** — `FormsProvider` wraps dashboard layout, `activeForm` shared between dashboard page and filter bar

---

## Phase 6: Landing Page, Layout Updates & Tests ✅

**Commits:** `7ccc562`, `a5e1f10`

### What was done

1. **Landing page** (`src/app/page.js`) — Dark background, large logo, title, subtitle, "Sign in to Dashboard" button linking to `/login`. No auto-redirect.

2. **Root layout** (`src/app/layout.js`) — Updated metadata: title "African Bamboo Dashboard", description with project tagline.

3. **Tests** (3 test suites, 10 tests total):
   - `__tests__/page.test.js` — Landing page: title, sign-in link, subtitle
   - `__tests__/login-form.test.js` — Login form: input fields, sign-in button, pre-filled URL, password toggle
   - `__tests__/filter-bar.test.js` — Filter bar: form selector, date range, reset button

4. **Jest config** — Added `transformIgnorePatterns` to handle `jose` ESM module

5. **Button UI polish** — Added `cursor-pointer`, `disabled:cursor-not-allowed`, `aria-busy:cursor-progress`

6. **Backend** — Added `region` and `woreda` fields to `SubmissionListSerializer`

### Key deviations
- **Landing page instead of redirect** — Original plan called for `redirect("/dashboard")`, implemented as a branded landing page with login button instead
- **No `submissions-table.test.js`** — Skipped in favor of filter-bar tests (submissions table requires complex mocking)

### Files created/modified
- `frontend/src/app/page.js` (rewritten)
- `frontend/src/app/layout.js` (metadata updated)
- `frontend/__tests__/page.test.js` (rewritten)
- `frontend/__tests__/login-form.test.js` (new)
- `frontend/__tests__/filter-bar.test.js` (new)
- `frontend/jest.config.mjs` (transformIgnorePatterns)
- `frontend/src/components/ui/button.jsx` (cursor states)
- `backend/api/v1/v1_odk/serializers.py` (region/woreda)

---

## Component Hierarchy (Actual)

```
RootLayout (src/app/layout.js)
├── / → Home (landing page with login button)
│
├── /login → LoginPage (server component)
│   └── LoginForm (client: useActionState + login Server Action)
│
├── /dashboard → DashboardLayout (server: verifySession → user+token)
│   ├── AuthProvider (client: sets axios token synchronously)
│   ├── FormsProvider (client: shared forms + activeForm state)
│   ├── AppSidebar (client: collapsible, mobile Sheet)
│   │   ├── Logo (inline SVG, currentColor)
│   │   ├── NavItem: Dashboard, Map, Forms
│   │   └── Footer: Support, Settings
│   └── <main>
│       ├── /dashboard → DashboardPage (client)
│       │   ├── DashboardHeader
│       │   ├── StatCard (x4)
│       │   ├── FilterBar (form dropdown controls activeForm)
│       │   ├── FormSectionHeader
│       │   ├── Tabs + Search
│       │   ├── SubmissionsTable + StatusBadge
│       │   └── TablePagination
│       ├── /dashboard/forms → FormsPage
│       │   ├── Register Form Card
│       │   └── Forms Table (with sync button)
│       ├── /dashboard/settings → SettingsPage
│       │   ├── Profile Card (read-only)
│       │   └── Logout Button
│       ├── /dashboard/map → MapPage (placeholder)
│       └── /dashboard/support → SupportPage (placeholder)
```

---

## State Management (Actual)

| State | Location | Persistence |
|-------|----------|-------------|
| Auth session (user, token) | jose-encrypted httpOnly cookie | Cookie (12h expiry) |
| Auth context (client) | `AuthContext` — user+token from server | In-memory |
| Forms list + activeForm | `FormsContext` via `FormsProvider` | In-memory (shared across dashboard) |
| Sidebar collapsed | `useState` in AppSidebar | None (resets on nav) |
| Active status tab | `useState` in DashboardPage | None |
| Search query | `useState` in DashboardPage | None |
| Submissions data | `useSubmissions` hook | None (refetched on param change) |

---

## File Summary (All files created/modified)

| Path | Purpose |
|------|---------|
| `frontend/components.json` | shadcn/ui config |
| `frontend/jest.config.mjs` | Jest config with jose ESM transform |
| `frontend/src/lib/utils.js` | `cn()` utility |
| `frontend/src/lib/session.js` | jose encrypt/decrypt + cookie management |
| `frontend/src/lib/dal.js` | `verifySession()` server-side DAL |
| `frontend/src/lib/api.js` | Axios client with token + 401 interceptor |
| `frontend/src/middleware.js` | Edge runtime route protection |
| `frontend/src/context/AuthContext.js` | Client-side user+token context |
| `frontend/src/hooks/useForms.js` | Context-based forms state with activeForm |
| `frontend/src/hooks/useSubmissions.js` | Submissions data fetching + pagination |
| `frontend/src/app/actions/auth.js` | login/logout Server Actions |
| `frontend/src/app/layout.js` | Root layout with metadata |
| `frontend/src/app/page.js` | Landing page with login button |
| `frontend/src/app/globals.css` | Tailwind v4 theming |
| `frontend/src/app/login/page.js` | Login page (server shell) |
| `frontend/src/app/login/login-form.js` | Login form (client, useActionState) |
| `frontend/src/app/dashboard/layout.js` | Dashboard layout (AuthProvider + FormsProvider) |
| `frontend/src/app/dashboard/page.js` | Dashboard content (stats, filters, table) |
| `frontend/src/app/dashboard/forms/page.js` | Forms management (register + sync) |
| `frontend/src/app/dashboard/settings/page.js` | Profile + logout |
| `frontend/src/app/dashboard/map/page.js` | Map placeholder |
| `frontend/src/app/dashboard/support/page.js` | Support placeholder |
| `frontend/src/components/app-sidebar.js` | Collapsible dark sidebar |
| `frontend/src/components/logo.js` | Inline SVG logo (currentColor) |
| `frontend/src/components/stat-card.js` | Stats card |
| `frontend/src/components/status-badge.js` | Approved/on_hold/rejected badge |
| `frontend/src/components/table-pagination.js` | Pagination controls |
| `frontend/src/components/filter-bar.js` | Form dropdown + date range |
| `frontend/src/components/dashboard-header.js` | Page header |
| `frontend/src/components/submissions-table.js` | Data table |
| `frontend/src/components/ui/*.jsx` | 14 shadcn/ui components |
| `frontend/public/logo.svg` | Logo asset (currentColor) |
| `frontend/__tests__/page.test.js` | Landing page tests (3) |
| `frontend/__tests__/login-form.test.js` | Login form tests (4) |
| `frontend/__tests__/filter-bar.test.js` | Filter bar tests (3) |
| `backend/api/v1/v1_odk/serializers.py` | Added region/woreda to submissions |

---

## Commit History

| Commit | Message |
|--------|---------|
| `318c9a2` | docs: Add technical execution plan |
| `b743ba6` | feat: Initialize shadcn/ui with Tailwind CSS v4 theming |
| `d0c2405` | feat: Add auth infrastructure with jose sessions, server actions, and middleware |
| `2418637` | feat: Add login page with KoboToolbox credentials form |
| `4bd34de` | feat: Add dashboard layout with collapsible dark sidebar |
| `c54e17a` | feat: Add dashboard content with stats, filters, submissions table, and settings |
| `12d7811` | fix: Resolve auth redirect loop by merging session crypto and fixing token race condition |
| `e483663` | feat: Add forms management page with sync, context-based form state, and sidebar nav update |
| `7ccc562` | feat: Add landing page with login button, update layout metadata, and add tests |
| `a5e1f10` | chore: Add button cursor states, lint shadcn components, and expose submission region/woreda |

---

## Verification

### Automated tests
```bash
cd frontend
yarn test    # 3 suites, 10 tests — all passing
yarn lint    # ESLint
yarn build   # Production build succeeds
```

### Manual testing checklist
1. Visit `http://localhost:3000` → Landing page with "Sign in to Dashboard" button
2. Click sign in → `/login` page
3. Enter invalid credentials → error message displayed
4. Enter valid KoboToolbox credentials → redirected to `/dashboard`
5. Dashboard shows sidebar, stats cards, filter bar, submissions table
6. Form dropdown in filter bar → changes active form, table updates
7. Sidebar toggle → collapses/expands
8. Navigate to `/dashboard/forms` → register form + forms table with sync
9. Click sync → submissions fetched from KoboToolbox
10. Navigate to `/dashboard/settings` → profile info + logout
11. Resize browser → responsive: mobile Sheet drawer, table horizontal scroll
12. Navigate directly to `/dashboard` without session → redirected to `/login`
