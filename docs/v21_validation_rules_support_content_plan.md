# V21 — Validation Rules Documentation & In-App Support Content

**Issue**: #41  
**Date**: 2026-04-06  
**Status**: Implemented
**Branch**: `feature/41-post-mvp-feedback-clarify-validation-rules-in-odk-app`

---

## Overview

Neither the ODK Android app nor the DCU Dashboard currently explains which validation rules are active. This plan implements a **single-source-of-truth** markdown file consumed by both apps, so field data collectors and data managers can understand why entries are flagged or rejected.

### Goals

1. Create a shareable validation rules markdown document
2. Render it in the DCU Dashboard Support tab
3. Add a new Support screen in the ODK Android app with the same content
4. Keep content consistent across both apps

---

## Architecture: Single Source of Truth

```
frontend/public/docs/validation-rules.md     ← Authoritative content
         │
         ├──► DCU App: fetch("/docs/validation-rules.md") at runtime
         │    (static file served by Next.js from public/)
         │
         └──► ODK App: Gradle task downloads at build time → assets/
              (configurable source URL in build.gradle.kts)
              Content is static inside the APK — no runtime fetching
```

### Why `frontend/public/docs/`?

- Next.js serves `public/` as static files — no API route needed
- Gradle build task can download the raw file from GitHub
- One file to update when rules change

### Why build-time fetch for ODK?

- Simpler app code — no network logic, no caching, no error states
- Works fully offline (content is bundled in the APK)
- Content updates ship with each APK release
- The source URL is configurable but nothing else needs to be

---

## Phase 1: Shared Markdown Content — DONE

### `frontend/public/docs/validation-rules.md`

Plain-language documentation covering:
- On-device rules (polygon geometry, plot overlap, blur detection)
- Post-sync rules (W1–W5 warning flags)
- FAQ section for common questions

The HTML comment at the top was removed to keep the served file clean.

---

## Phase 2: DCU Dashboard — Support Tab Update — DONE

### Step 2.1 — Dependencies installed

```bash
cd frontend && yarn add react-markdown remark-gfm
```

- `react-markdown@^10.1.0`
- `remark-gfm@^4.0.1`

### Step 2.2 — `ValidationRulesContent` component

**File**: `frontend/src/components/validation-rules-content.js`

```jsx
"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { VALIDATION_RULES_URL } from "@/lib/constants";

const markdownComponents = {
  h1: ({ children }) => (
    <h1 className="text-xl font-bold mt-6 mb-2">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-lg font-semibold mt-5 mb-2">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-base font-semibold mt-4 mb-1">{children}</h3>
  ),
  p: ({ children }) => (
    <p className="text-sm leading-relaxed mb-3">{children}</p>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-4">
      <table className="w-full text-sm border-collapse">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border px-3 py-1.5 bg-muted text-left font-medium text-xs">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border px-3 py-1.5 text-xs">{children}</td>
  ),
  ul: ({ children }) => (
    <ul className="list-disc pl-5 space-y-1 text-sm mb-3">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal pl-5 space-y-1 text-sm mb-3">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="text-sm [&>p]:mb-0">{children}</li>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold">{children}</strong>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-muted-foreground/30 pl-4 italic text-sm text-muted-foreground my-3">
      {children}
    </blockquote>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      className="text-primary underline hover:text-primary/80"
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono">
      {children}
    </code>
  ),
  hr: () => <hr className="my-4 border-border" />,
};

const ValidationRulesContent = () => {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(VALIDATION_RULES_URL)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load");
        return res.text();
      })
      .then((text) => {
        if (!cancelled) setContent(text);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // ... loading/error states, then:
  return (
    <div className="max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={markdownComponents}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default ValidationRulesContent;
```

Key design decisions:
- `markdownComponents` extracted as a **static object outside the component** to avoid re-creation on every render
- **No `prose` wrapper** — all elements styled explicitly via `markdownComponents` overrides (including `a`, `code`, `hr`), so `@tailwindcss/typography` is not needed
- `li` uses `[&>p]:mb-0` to suppress `mb-3` from `<p>` tags that `react-markdown` wraps inside list items
- `VALIDATION_RULES_URL` imported from `@/lib/constants` (not hardcoded)
- Cleanup function (`cancelled = true`) prevents state updates on unmounted component
- `ol` override included alongside `ul` for future-proofing
- No `@tailwindcss/typography` needed — all styles via Tailwind utility classes in custom components

### Step 2.3 — Support page integration

**File**: `frontend/src/app/dashboard/support/page.js`

Added a "Validation Rules" Card between "Contact Support" and "Helpful Resources":

```jsx
import { ShieldCheck } from "lucide-react";
import ValidationRulesContent from "@/components/validation-rules-content";

<Card>
  <CardHeader>
    <CardTitle className="flex items-center gap-2">
      <ShieldCheck className="size-5" />
      Validation Rules
    </CardTitle>
    <CardDescription>
      Active validation rules for data collection and quality checks
    </CardDescription>
  </CardHeader>
  <CardContent>
    <ValidationRulesContent />
  </CardContent>
</Card>
```

### Step 2.4 — Constant added

**File**: `frontend/src/lib/constants.js`

```js
/** URL to the shared validation rules markdown (served from public/docs/). */
export const VALIDATION_RULES_URL = "/docs/validation-rules.md";
```

---

## Phase 3: ODK Android App — Support Screen — IN PROGRESS

### Step 3.1 — Gradle task to download content at build time

**File**: `ODKApps/.../app/build.gradle.kts`

```kotlin
val supportContentUrl: String = project.findProperty(
    "supportContentUrl"
) as? String
    ?: ("https://raw.githubusercontent.com/" +
        "akvo/african-bamboo-dashboard/" +
        "main/frontend/public/docs/validation-rules.md")

tasks.register("downloadSupportContent") {
    description = "Downloads validation rules markdown from the DCU repo"
    val outputFile = file("src/main/assets/validation-rules.md")

    doLast {
        try {
            val conn = java.net.URI(supportContentUrl).toURL()
                .openConnection() as java.net.HttpURLConnection
            conn.connectTimeout = 10_000
            conn.readTimeout = 10_000
            conn.inputStream.use { input ->
                outputFile.outputStream().use { output ->
                    input.copyTo(output)
                }
            }
            logger.lifecycle(
                "Downloaded support content to ${outputFile.path}"
            )
        } catch (e: Exception) {
            if (outputFile.exists()) {
                logger.warn(
                    "Download failed, keeping existing: ${e.message}"
                )
            } else {
                logger.warn(
                    "Download failed, no fallback: ${e.message}"
                )
                outputFile.writeText(
                    "# Validation Rules\n\n" +
                        "Content unavailable. " +
                        "Visit the project documentation."
                )
            }
        }
    }
}

tasks.matching {
    it.name.startsWith("merge") && it.name.endsWith("Assets")
}.configureEach {
    dependsOn("downloadSupportContent")
}
```

Key details:
- 10-second connect/read timeout to prevent build hangs
- Three-tier fallback: download → keep existing → write minimal placeholder
- Configurable via `gradle.properties` or CLI: `./gradlew assembleDebug -PsupportContentUrl=...`

### Step 3.2 — `compose-markdown` dependency

**File**: `ODKApps/.../gradle/libs.versions.toml`

```toml
composeMarkdown = "0.5.4"
compose-markdown = { module = "com.mikepenz:multiplatform-markdown-renderer-m3", version.ref = "composeMarkdown" }
```

**File**: `ODKApps/.../app/build.gradle.kts`

```kotlin
// Markdown renderer for Support screen
implementation(libs.compose.markdown)
```

### Step 3.3 — Navigation route

**File**: `navigation/Routes.kt`

```kotlin
@Serializable
object Support
```

### Step 3.4 — `SupportScreen`

**File**: `ui/screen/SupportScreen.kt`

```kotlin
package org.akvo.afribamodkvalidator.ui.screen

import android.content.Context
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.mikepenz.markdown.m3.Markdown
import org.akvo.afribamodkvalidator.ui.theme.AfriBamODKValidatorTheme

private const val ASSET_FILE = "validation-rules.md"

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SupportScreen(
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val markdownContent = remember {
        loadMarkdownFromAssets(context)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Support") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector =
                                Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back"
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor =
                        MaterialTheme.colorScheme.surface,
                    titleContentColor =
                        MaterialTheme.colorScheme.onSurface
                ),
                windowInsets = WindowInsets(0)
            )
        },
        modifier = modifier
    ) { innerPadding ->
        Markdown(
            content = markdownContent,
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        )
    }
}

private fun loadMarkdownFromAssets(context: Context): String {
    return try {
        context.assets
            .open(ASSET_FILE)
            .bufferedReader()
            .use { it.readText() }
    } catch (e: Exception) {
        "# Validation Rules\n\nUnable to load content."
    }
}
```

Key design decisions:
- No ViewModel needed — content is a static bundled asset, loaded once via `remember`
- TopAppBar uses `surface`/`onSurface` colors to match `SettingsScreen`
- `com.mikepenz.markdown.m3.Markdown` handles full GFM rendering

### Step 3.5 — Menu item in `HomeDashboardScreen`

**File**: `ui/screen/HomeDashboardScreen.kt`

Added `onSupportClick: () -> Unit` to both outer and inner composable signatures. Menu item added between Settings and Logout (with `HorizontalDivider` before Logout):

```kotlin
DropdownMenuItem(
    text = { Text("Settings") },
    onClick = { showMenu = false; onSettingsClick() }
)
DropdownMenuItem(
    text = { Text("Support") },
    onClick = { showMenu = false; onSupportClick() }
)
HorizontalDivider()
DropdownMenuItem(
    text = { Text("Logout") },
    onClick = { showMenu = false; showLogoutDialog = true }
)
```

All 4 `@Preview` composables updated with `onSupportClick = {}`.

### Step 3.6 — Route registration in `AppNavHost`

**File**: `navigation/AppNavHost.kt`

```kotlin
composable<Support> {
    SupportScreen(
        onBack = { navController.popBackStack() }
    )
}
```

`composable<Home>` updated with `onSupportClick = { navController.navigate(Support) }`.

### Step 3.7 — Generated asset gitignored

**File**: `ODKApps/.../app/.gitignore`

```
# Generated at build time by downloadSupportContent task
src/main/assets/validation-rules.md
```

---

## Phase 4: Build & Content Flow

### How content flows at build time (ODK App)

```
┌─────────────────────────────────────────────┐
│              Gradle Build                    │
│                                              │
│  1. downloadSupportContent task runs         │
│     ↓                                        │
│  2. Fetches from supportContentUrl           │
│     (10s timeout, fallback on failure)       │
│     ↓                                        │
│  3. Saves to src/main/assets/                │
│     validation-rules.md                      │
│     ↓                                        │
│  4. mergeDebugAssets / mergeReleaseAssets     │
│     bundles it into the APK                  │
│     ↓                                        │
│  5. App reads from assets at runtime         │
│     (no network needed)                      │
└─────────────────────────────────────────────┘
```

### How content flows at runtime (DCU App)

```
┌─────────────────────────────────────────────┐
│              Browser / Next.js               │
│                                              │
│  1. User opens /dashboard/support            │
│     ↓                                        │
│  2. ValidationRulesContent mounts            │
│     ↓                                        │
│  3. fetch("/docs/validation-rules.md")       │
│     (served from public/ as static file)     │
│     ↓                                        │
│  4. ReactMarkdown renders the content        │
└─────────────────────────────────────────────┘
```

### Content update workflow

```
Developer updates frontend/public/docs/validation-rules.md
         │
         ├──► DCU: Deploys with next frontend build (automatic)
         │
         └──► ODK: Next APK build downloads fresh copy
              (CI/CD or local ./gradlew assembleRelease)
```

---

## File Change Summary

### New Files

| File | App | Description |
|------|-----|-------------|
| `frontend/public/docs/validation-rules.md` | DCU | Shared validation rules content (source of truth) |
| `frontend/src/components/validation-rules-content.js` | DCU | Markdown fetcher + renderer component |
| `ODKApps/.../ui/screen/SupportScreen.kt` | ODK | New Support screen (reads from assets) |

### Modified Files

| File | App | Change |
|------|-----|--------|
| `frontend/src/app/dashboard/support/page.js` | DCU | Add ValidationRulesContent card |
| `frontend/src/lib/constants.js` | DCU | Add `VALIDATION_RULES_URL` constant |
| `frontend/package.json` | DCU | Add `react-markdown`, `remark-gfm` |
| `ODKApps/.../app/build.gradle.kts` | ODK | Add `downloadSupportContent` task + `compose-markdown` dep |
| `ODKApps/.../gradle/libs.versions.toml` | ODK | Add `composeMarkdown` version entry |
| `ODKApps/.../navigation/Routes.kt` | ODK | Add `Support` route object |
| `ODKApps/.../navigation/AppNavHost.kt` | ODK | Register `Support` composable + pass `onSupportClick` |
| `ODKApps/.../ui/screen/HomeDashboardScreen.kt` | ODK | Add `onSupportClick` param + menu item |
| `ODKApps/.../app/.gitignore` | ODK | Ignore generated `validation-rules.md` asset |

### Generated Files (build-time, gitignored)

| File | Description |
|------|-------------|
| `ODKApps/.../src/main/assets/validation-rules.md` | Downloaded at build time from DCU repo |

---

## Decisions Made

### Build-time fetch for ODK (not runtime)

The ODK app downloads validation rules markdown **during the Gradle build**, not at runtime.

**Why:**
- No network logic in the app — simpler code, no ViewModel needed
- Works fully offline — content is a bundled asset
- No loading spinners, no error states, no caching
- Content updates ship with each APK release (acceptable cadence)
- Source URL is configurable via `gradle.properties` or CLI flag

### Markdown library: `com.mikepenz:multiplatform-markdown-renderer-m3`

**Why:**
- Full GFM support (tables, headers, bold, lists, blockquotes)
- Material 3 native — matches the app's existing design system
- Active maintenance, widely used in Compose projects
- ~200KB added to APK — acceptable tradeoff

### Overlap threshold documented as read-only

The 20% overlap threshold is hidden from the Settings screen (intentionally non-adjustable by enumerators). It **is** documented in the Support tab because users should understand why submissions are rejected.

### No `@tailwindcss/typography` for DCU

The `ValidationRulesContent` component uses a static `markdownComponents` object that explicitly styles every rendered element (`h1`–`h3`, `p`, `table`, `th`, `td`, `ul`, `ol`, `li`, `strong`, `blockquote`, `a`, `code`, `hr`) via Tailwind utility classes. No `prose` wrapper is used, so `@tailwindcss/typography` is not a dependency. This avoids potential conflicts with Tailwind CSS v4's configuration format and gives full styling control.

---

## Testing Checklist

### DCU Dashboard

- [ ] `http://localhost:3000/docs/validation-rules.md` returns raw markdown
- [ ] Support page renders validation rules card with formatted content
- [ ] Tables render correctly with borders and headers
- [ ] Loading spinner appears briefly before content loads
- [ ] Error message shown if file is missing
- [ ] Content is readable on mobile viewport

### ODK Android App

- [ ] `./gradlew downloadSupportContent` downloads the file to `assets/`
- [ ] `./gradlew assembleDebug` includes `validation-rules.md` in APK
- [ ] Build succeeds even when download URL is unreachable (fallback works)
- [ ] Build works with custom URL: `./gradlew assembleDebug -PsupportContentUrl=...`
- [ ] Support menu item appears in overflow menu (⋮)
- [ ] Support screen opens and shows formatted content
- [ ] Tables render correctly in Compose markdown
- [ ] Back navigation returns to Home dashboard
- [ ] TopAppBar style matches Settings screen

### Cross-App Consistency

- [ ] Same validation rules listed in both apps
- [ ] Same FAQ content in both apps
- [ ] Updating `frontend/public/docs/validation-rules.md` reflects in DCU immediately
- [ ] Rebuilding ODK APK picks up the updated content
