# Brand application

Every visual surface of this project follows the DNR identity system
(`docs/brand/ManualIdentidadMarcaDNR_v2.pdf`, v2.0, July 2026): the slide deck and its PDF,
the Streamlit app, the README imagery and the charts in the notebook. This file records how
the manual maps onto each surface and where a judgement call was needed. It follows the
same approach as the FAERS GLP-1 project's brand application, so the two projects read as
one body of work.

## Assets (`docs/brand/`)

| File | Manual family × finish | Used for |
|---|---|---|
| `SimpleClaro.png` | Simple · Claro (navy structure, copper N) | light surfaces: README header (light theme), Streamlit logo, footer mark on light slides |
| `SimpleOscuro.png` | Simple · Oscuro (platinum structure, amber N) | dark surfaces: README header (dark theme), footer mark on dark slides |
| `ComplejoOscuro.png` | Complejo · Oscuro | cover slide only (large format, ≥ 300 px as §11 requires) |
| `ComplejoClaro.png` | Complejo · Claro | kept for a light-background cover if one is ever needed |
| `favicon.png`, `favicon64x64.png` | the isolated N | browser tab icon and collapsed-sidebar icon of the app |

The files are the official logos trimmed to the mark and resized (800 px wide for Simple,
1,200 px for Complejo) with a transparent clear-space margin of one node diameter on every
side (manual §11). No colour, proportion or effect was changed. The *Medio* (metallic)
finishes are not used: the manual restricts them to large-format hero pieces, and the only
large-format surface here is the cover, which is dark.

## Colour roles

Light mode and dark mode are both sanctioned; the deck alternates them (dark cover, demo and
closing; light content slides) and the app is light.

| Role | Light surfaces | Dark surfaces |
|---|---|---|
| Canvas | `#E2E8F0` (upper end of the light range, §2) | `#0F141C` Azul Grafito — never `#000000` |
| Card / surface | `#FAFAFA` Blanco Nieve, 1 px `#CBD5E1` edge | `#1E2530`, 1 px `#2D3748` edge (§8, project cards) |
| Headings | `#162B43` Azul Medianoche | `#E2E8F0` Platino |
| Body | `#2C3E50` Antracita | `#CBD5E1` Gris Neutro |
| Secondary | `#64748B` Gris Slate — inside `#FAFAFA` cards only | `#94A3B8` Aluminio (Slate fails AA on `#0F141C`) |
| Accent | `#B95319` Naranja Cobre | `#E65F19` Naranja Ámbar |
| Accent on a navy card | `#E29A5C` (top of the copper ramp, §5) | — |
| Ink-on-accent | white on `#B95319` (4.87:1) | `#0F141C` on `#E65F19` (5.29:1); white only ≥ 18 px |

Two consequences the manual spells out and this project keeps:

* **Small text on the light canvas is Antracita, not Slate.** Slate is 4.56:1 on `#FAFAFA`
  but only 3.86:1 on `#E2E8F0`, so slide footers (24 px) use `#2C3E50`.
* **Dark-finish logos never sit on light backgrounds** and vice versa (§2, §10). The README
  swaps them with `<picture>` + `prefers-color-scheme`.

## Charts: accent-plus-structure, not categorical

The manual gives no categorical palette and, as the previous project showed with a palette
validator, it should not: navy is ink, not a series fill. The rule used here:

* **In-domain = copper**, in two ramp stops when a second in-domain group is needed
  (English `#8C4516`, Spanish `#B95319`); **out-of-domain = Slate `#64748B`**, "the rest".
* The refusal gate is a dashed **navy** line; axes and ticks Slate; background equal to the
  canvas (`#FAFAFA`), never white on a dark page.

This applies to the calibration dot plot on the evaluation slide and in the notebook, and to
the chunk-length histogram (single series, copper, no legend).

## Deck

* Typography: **Inter** (titles 700/800, body 400) for everything; **JetBrains Mono** for
  graph node names and file paths (manual §7). Both from Google Fonts at render time; the
  PDF embeds them.
* The architecture diagram: `rewrite_query` / `retrieve` as navy cards with copper-ramp
  labels, `generate` navy, `refuse` solid copper with white text, connectors Slate with the
  grounded branch in navy and the below-gate branch in copper.
* Flat colours only: no gradients, shadows, glow or neon (§6). Cards get a 1 px edge for
  separation instead of a shadow.
* Logos: `ComplejoOscuro` bottom-right on the cover (380 px), `SimpleOscuro` on the closing
  slide (200 px), `SimpleClaro` at 150 px on every light slide — all above the §11 minimums.

## Streamlit app

`.streamlit/config.toml` carries the whole theme: `primaryColor #B95319`, canvas `#FAFAFA`,
secondary `#E2E8F0`, text `#2C3E50`, links and focus copper, borders `#CBD5E1`, radius
*medium*. Inter and JetBrains Mono are self-hosted latin subsets (`static/fonts/`, SIL OFL)
served through `enableStaticServing`, so the demo does not depend on Google Fonts. The app
shows `SimpleClaro` as `st.logo` (the isolated N when the sidebar is collapsed), the N as
tab icon, and a 2 px copper rule under the page title — the one structural use of copper
(§8, header band).

## Checked against §12 (Do / Don't)

No radial gradients, glow, diffuse shadows or neon. No pure black. *Claro* logos on light
backgrounds, *Oscuro* on dark ones. Clear space and minimum sizes respected. Every new
colour combination recomputed against WCAG 2.1 AA before use (table above).
