# design.md — Colors, Theme, Fonts & Typography

**Project:** SENTRY — AI-Based Fake Identity & Document Screening System
**Last updated:** 2026-08-27
**Source of truth:** these tokens are already defined in `style.css` (`:root`).
This file documents them so all new UI stays consistent. **Match these — don't
invent new colors.**

---

## 1. Design language
A **border-checkpoint terminal / security-console** aesthetic: dark, calm,
data-dense, monospace accents, subtle scanline/grid motifs, restrained glow on
interactive elements. Serious and trustworthy — this is a security tool.

## 2. Color tokens

### Dark theme (default)
| Token | Hex | Use |
|-------|-----|-----|
| `--void` | `#0A0D10` | App background (with faint grid) |
| `--panel` | `#10151A` | Cards, sidebar, panels |
| `--panel-raised` | `#151C22` | Raised surfaces, chips, hover |
| `--line` | `#1E262C` | Default borders/dividers |
| `--line-bright` | `#2A343B` | Stronger borders, inputs |
| `--text` | `#E7ECEF` | Primary text |
| `--text-dim` | `#8B99A3` | Secondary text |
| `--text-faint` | `#54626C` | Labels, captions, mono meta |
| `--amber` | `#FFB020` | **Primary brand / CTA** (buttons, logo, active nav) |
| `--amber-dim` | `#7A5A19` | Muted amber backgrounds |
| `--cyan` | `#3FE0D0` | **Secondary accent** (focus, links, active/scan states) |
| `--cyan-dim` | `#1D5C55` | Muted cyan backgrounds/borders |
| `--low` | `#34D399` | Risk LOW / success (green) |
| `--med` | `#FBBF24` | Risk MED / warning (yellow) |
| `--high` | `#F5576C` | Risk HIGH / danger (red) |

### Light theme (`body.theme-light` override)
| Token | Hex |
|-------|-----|
| `--void` | `#F3F5F6` |
| `--panel` | `#FFFFFF` |
| `--panel-raised` | `#F0F3F5` |
| `--line` | `#E1E7EA` |
| `--line-bright` | `#CBD5DA` |
| `--text` | `#161B1F` |
| `--text-dim` | `#5B6770` |
| `--text-faint` | `#8C99A2` |
| `--amber` | `#C97F00` |
| `--amber-dim` | `#F0DCB2` |
| `--cyan` | `#0E9488` |
| `--cyan-dim` | `#D3F1EC` |
| `--low` | `#0F9D6B` |
| `--med` | `#B9860B` |
| `--high` | `#D93655` |

Theme is toggled via `toggleTheme()` in `app.js`; both themes must stay legible.

### Color usage rules
- **Amber = primary action / brand.** One primary (amber) button per view.
- **Cyan = interactive/system state** (focus rings, active pipeline node, scan
  animations, links). Not a CTA color.
- **Risk colors are semantic only** — never use green/yellow/red decoratively.
  LOW=green, MED=amber-yellow, HIGH=red, consistently everywhere.

## 3. Typography
| Role | Font | Weights | Used for |
|------|------|---------|----------|
| Display | **Space Grotesk** | 400–700 | Headings, brand, stat numbers, panel titles |
| Body | **Inter** | 400–600 | Paragraphs, labels, buttons, general UI |
| Mono | **JetBrains Mono** | 400–700 | IDs, codes, timestamps, metadata, tags, eyebrows |

Loaded via Google Fonts in `index.html`. CSS vars: `--font-display`,
`--font-body`, `--font-mono`.

### Type scale (from existing CSS)
- Page title `h1.page-title`: 24px / 700 / Space Grotesk / letter-spacing -.01em
- Page subtitle `.page-sub`: 13px / `--text-dim`
- Panel title: 14px / 600 / Space Grotesk
- Stat number: 28px / 700 / Space Grotesk
- Body/table text: 12.5–13px / Inter
- Eyebrow / mono labels: 10–11px / JetBrains Mono / letter-spacing .1–.14em / uppercase
- Risk chips: 10px / 700 / JetBrains Mono

**Convention:** anything machine-ish (document IDs, times, checksums, field
labels) → mono + faint + letterspaced. Human-readable content → Inter.

## 4. Core components (already styled — reuse them)
- **Buttons** `.btn`: radius 6px. `.btn-primary` (amber), `.btn-danger` (red
  outline), `.btn-ghost`, `.btn-block`, `.btn-disabled`. Hover shifts to cyan.
- **Cards** `.card`: `--panel` bg, `--line` border, radius 10px, padding 20px.
- **Risk chips** `.risk-chip` + `.risk-low/.risk-med/.risk-high`: pill, tinted bg.
- **Stat cards** `.stat-card`: left accent bar colored cyan/green/amber/red by position.
- **Pipeline** `.pnode` with `.done` (green) / `.active` (cyan, pulsing) states.
- **Gauge** `.gauge`: SVG ring; color driven by risk tier.
- **Flags** `.flag-item` (+`.warn`): red by default, amber when `.warn`.
- **Check items** `.check-item`: `.checking` (cyan pulse) / `.pass` (green) /
  `.flagged` (amber) — used in liveness & user verification lists.
- **Inputs** `.field input`: void bg, mono text, cyan focus ring.
- **AI disclaimer** `.ai-disclaimer`: dashed box — **keep on AI-output screens.**

## 5. Motion
- Fade-up on view change (`fadeUp .35s`).
- Scanline animations on brand mark & face frames (`scanY`, `sweepY`).
- Pulse on active/checking states.
- Keep motion subtle; never block reading. When wiring real data, drive the
  pipeline `.done`/`.active` classes from actual step completion.

## 6. Layout
- Sidebar 220px fixed + fluid main; topbar 56px with checkpoint pill + live clock.
- Grid backdrop (48px) on `--void`. Cards on `--panel`. Generous 18–24px gaps.
- Content padding ~28–32px; max readable width for text blocks.

## 7. Rules for new UI
1. Use existing tokens/classes; do not hard-code hex values.
2. New pages must work in **both** themes.
3. Preserve the "AI advisory" disclaimers on any screen showing AI output.
4. Keep the mono-for-machine / Inter-for-humans split.
5. Prefer extending existing components over creating new visual patterns.
