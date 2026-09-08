# UI_GAP — UI_SPEC against the current build

Every row of `UI_SPEC.md` set against branch FD-362 at the audited commit. Build evidence comes from the two audits of that branch, one read from source and one measured from the page running in headless Chromium at 390x844. Where neither audit covers a row it says UNCHECKED rather than guessing.

Statuses: **MET** the build matches the spec value · **PARTIAL** part of it is there · **CHANGED** the build does something different · **MISSING** absent · **UNCHECKED** no evidence either way · **N/A** the row is a superseded option, an unpicked option, or a conflict with no pick, so there is nothing for the build to match.

| status | rows |
|---|---|
| MET | 114 |
| PARTIAL | 35 |
| CHANGED | 66 |
| MISSING | 107 |
| UNCHECKED | 57 |
| N/A | 61 |
| **total** | **440** |

| group | MET | PARTIAL | CHANGED | MISSING | UNCHECKED | N/A |
|---|---|---|---|---|---|---|
| 1. App shell and navigation | 4 | 3 | 4 | 6 | 4 | 4 |
| 2. Sessions / discussions drawer | 0 | 0 | 0 | 25 | 3 | 11 |
| 3. Settings and account | 0 | 2 | 0 | 24 | 1 | 9 |
| 4. Picture at rest — the sentence spotlight | 34 | 3 | 8 | 2 | 4 | 6 |
| 5. Picture symbols — one row per symbol | 9 | 8 | 25 | 13 | 3 | 4 |
| 6. Chalkboard / moves board | 4 | 2 | 4 | 11 | 4 | 3 |
| 7. Show-tool view kinds | 1 | 5 | 1 | 0 | 0 | 0 |
| 8. Play-by-play | 5 | 5 | 6 | 6 | 5 | 0 |
| 9. Chips | 11 | 1 | 3 | 1 | 3 | 2 |
| 10. Chat bubbles and layout | 12 | 2 | 3 | 1 | 1 | 6 |
| 11. List view and event editor | 10 | 1 | 5 | 3 | 7 | 2 |
| 12. Type and colour tokens | 9 | 2 | 4 | 0 | 2 | 1 |
| 13. Animation and timing | 2 | 1 | 3 | 10 | 6 | 2 |
| 14. Tap and scroll behaviour | 9 | 0 | 0 | 5 | 3 | 3 |
| 15. Other | 4 | 0 | 0 | 0 | 11 | 8 |

## 1. App shell and navigation

| element | spec value | build value | status |
|---|---|---|---|
| Phone frame | 400x820px, max-width 100%, background `--panel`, border 1px `--line`, border-radius 26px, box-shadow `0 8px 40px var(--shadow)`, overflow hidden, `… | Web page, no phone frame; app frame 460px with a border above the breakpoint | CHANGED |
| Phone frame, alternate | 390px wide, border-radius 36px, padding 10px, box-shadow `0 18px 40px -22px rgba(20,30,34,.35)` | not applicable (no pick to build) | N/A |
| Screen layer | absolute inset 0, `transition: transform .24s ease, filter .24s ease` | — | UNCHECKED |
| Status bar | padding `10px 22px 2px`, font `600 13px -apple-system, system-ui`; time "9:41"; icons gap 5px, signal 16x10px clip-path bars, wifi 14x10px half-pil… | Browser chrome, no simulated status bar | N/A |
| App header ("Family Diagram" bar) | — | No app header | MET |
| Title row | height 44px, padding `0 14px`, border-bottom 1px `--line`, flex, gap 10px, directly under the status bar and above the picture | 44px row: title plus one hamburger button | PARTIAL |
| Title text | `600 15px/1.2 "Libre Franklin"`, colour `--ink`, flex 1, ellipsis overflow | Hardcoded "Your family" | PARTIAL |
| Title text size | 15px in every built mockup against the binding 17/600 screen-title floor | — | UNCHECKED |
| Title default text | the current diagram/family name, e.g. "your family" or a professional's client diagram name | Hardcoded "Your family"; never changes, never shows the diagram name | PARTIAL |
| Account avatar | 44x44px circle, border-radius 50%, background `--panel`, border `1.5px solid var(--data)`, colour `--data`, initial in `500 13px "IBM Plex Mono"`,… | No avatar; the upper right holds a hamburger labelled Timeline and settings | CHANGED |
| Avatar size | UI_STANDARDS.md and API2.md prose say a 30px (standards text says 40px) visual inside a 44x44 target; the built CSS fills the whole 44 | No avatar to size | MISSING |
| Avatar correction | the account avatar was too small and must meet the shared size standard | No avatar to size | MISSING |
| Nav button (back / close) | 44x44px, font `600 18px system-ui`, colour `--data`, no border or background | No picture-level nav buttons; there are no picture levels | MISSING |
| Back chevron, settings stack | `‹`, min 44x44px, colour `--data`, font `500 19px mono`, inserted at the start of the title row | No settings stack | MISSING |
| Picture-region corner slots | `.corner` absolute top 2px; `.l{left:4px}`, `.r{right:4px}`; each holds a nav slot and a concept slot | No corner slots | MISSING |
| Crumb line | `500 13px "IBM Plex Mono"`, colour `--faint`, min-height 15px, centred; sentence-spotlight sets `margin: 0 48px` to clear the corner buttons | No crumb; a pin label row carries the picture state instead | CHANGED |
| Crumb line, coach-screen variant | `500 10.5px mono`, min-height 15px, padding `0 4px`, link colour `--data` no underline | not applicable (no pick to build) | N/A |
| Bottom tab bar | 50px height, absolute bottom 0, border-top 1px `--line`, 2 tabs x 200px, icon 20x20 + 10px label, active `--data`, inactive `--faint` | Absent | N/A |
| Signed-out screen | full-phone overlay z-index 25, centred column gap 16px; app name `800 21px "Libre Franklin"`; who line `500 13px mono`; sign-in pill border 1px `--… | No signed-out screen and no sign-out control | MISSING |
| Focus ring, global | `outline: 2px solid var(--data)`, offset 1px, and -2px inside picture hit zones | outline 2px var(--data) offset 1px, -2px on picture hit zones | MET |
| Pressed state, global | every interactive element has a visible pressed state | — | UNCHECKED |
| Button and icon consistency | every button and icon meets one shared size and usability standard | — | UNCHECKED |
| App frame width, web | FD-360 720px; chat-first-app 420px; FD-362 460px, each with a border above the breakpoint | 460px | MET |
| PWA shell | manifest, service worker at `/companion/sw.js`, `icon.svg`, Google Fonts preconnect | manifest, service worker, icon, font preconnect | MET |
| Menu button label | a control's label must name what it does | Labelled "Timeline and settings"; opens a timeline list with no settings in it | CHANGED |

## 2. Sessions / discussions drawer

| element | spec value | build value | status |
|---|---|---|---|
| Session door — the pick | the button plus a swipeable, searchable sessions overlay, as built in the `family-sections` option | No sessions surface of any kind | MISSING |
| Door placement | beside the chat input, not in the title row | The input bar is a composer plus a send button only | MISSING |
| Sessions button, final look | 34px circle, hairline 1px `--line` border, `--bg` fill, three-line icon 16x12 (`M1 1h14M1 6h14M1 11h14`) stroke 1.6 round caps at 80% opacity, insi… | No sessions button anywhere | MISSING |
| Sessions glyph, as built in the avatar round | `.sessglyph` 44x44px, no border or background, font-size 22px | not applicable (superseded) | N/A |
| Sessions bottom sheet | height 92% of the frame (top edge y=66), background `--panel`, border-radius `18px 18px 0 0`, box-shadow `0 -8px 30px var(--shadow)`, `transform: t… | No overlay, no sheet, no scrim | MISSING |
| Sheet grabber | 36x5px, border-radius 3px, `--line`, in a 22px handle strip | Absent | MISSING |
| Sheet open / close gestures | drag up from the input bar 40px or more opens; tap the scrim closes | Absent | MISSING |
| Sheet search field | 36px high, border-radius 18px pill, 13.5px, border 1px `--line`, focus border `--data`, placeholder "Search sessions and families" | No search | MISSING |
| Search field size | 36px high and 13.5px text against the binding 44px control height and 17px text-field value | Absent | MISSING |
| Family section header | 40px sticky, family name `600 13px`, 60x14px wire thumbnail, "last: <summary>" `10.5px mono`, a 28x28px green "+" at the right | No sessions list in the page | MISSING |
| Family section rows | 54px, sorted by recency, no Today/Yesterday subgroups inside a family, each family collapsed to its 3 most recent plus a 36px "N more…" row | Absent | MISSING |
| Session row, default | height 56px, padding `0 14px 0 16px`, border-bottom 1px `--line`, background `--panel` | Absent | MISSING |
| Session row, title-and-date only | height 44px, no summary line | not applicable (no pick to build) | N/A |
| Session row, with wire thumbnail | height 60px, adds a 48x12px wire thumbnail at the left and a 10px mono picture-state word under the date | not applicable (no pick to build) | N/A |
| Row title | `15px/1.3`, nowrap ellipsis, ~30 chars; untitled shown in `--faint` | Absent | MISSING |
| Row summary | `12.5px/1.3`, `--faint`, nowrap ellipsis | Absent | MISSING |
| Row side / date | `500 10.5px/1.3 mono`, `--faint`, tabular-nums, max-width 44% | Absent | MISSING |
| Row side text size | 10.5px against the binding 13px absolute floor | Absent | MISSING |
| Current-session marker | `::before` 3px left bar in `--data`, full row height | Absent | MISSING |
| Row press feedback | background `--tint` | Absent | MISSING |
| Renamed-row marker | `✎` glyph, 9px, `--faint`, 4px left margin | Absent | MISSING |
| Sticky group header | position sticky top 0, height 20px, line-height 20px, padding `0 16px`, `500 10.5px mono`, uppercase, letter-spacing .04em, `--faint`, background `… | Absent | MISSING |
| Rename, inline field | `15px/1.3 Libre Franklin`, colour `--ink`, background `--bg`, border 1px `--data`, border-radius 4px, padding `1px 6px`, text pre-selected | No rename | MISSING |
| Rename revert target | revert to the coach's auto title, or to the previous title | Absent | MISSING |
| New-session button | pinned in the sheet footer, full width, 40px high, border `1.5px solid var(--move)`, border-radius 20px, green label "New session with <family>" | No way to start a new session from the page | MISSING |
| Empty states, verbatim | "Past conversations collect here" when there are none; "No sessions match" when a search finds none. Mono 11px, `--faint`, centred, 18px padding | Absent | MISSING |
| Sort order | newest activity first; never reorders while the view is open | — | UNCHECKED |
| Another user's session | returns 404, not 403 | — | UNCHECKED |
| `Discussion.title` | nullable column, auto-titled by the coach after the first exchange, hand-editable | — | UNCHECKED |
| Two-way traceability, picture to session | a selected moment shows a chip reading `coded in: <session title> · <short date> →`, title truncated at 30 chars | Caption offers only Ask about this and Play; no coded-in chip, no session jump, no traced outline | MISSING |
| Toast | `500 13px mono` (11px in scaffold), background `--ink`, colour `--panel`, border-radius 14px, padding `6px 12px`, opacity 0 to .92 over .2s, auto-d… | No toast container found | MISSING |
| Card-stack list aesthetic | 300x180px cards, radius 14px, 60px overlap, Safari-tab-stack shadow | not applicable (no pick to build) | N/A |
| Corner drawer | 320px wide drawer from the left, 240ms slide, screen shifts right 40px and dims 30%; 18px `≡` in the left picture corner | not applicable (no pick to build) | N/A |
| Swipe deck | horizontal drag on chat, previous session slides in behind at scale 0.94, 320ms spring | not applicable (no pick to build) | N/A |
| Crumb title | crumb becomes a tappable title, panel drops from the picture's bottom edge over 220ms, 376px wide | not applicable (no pick to build) | N/A |
| Pull the picture down | 24x4px grabber in the picture's caption strip, drag past 60px springs the list open over 300ms | not applicable (no pick to build) | N/A |
| Ask the coach | no visible UI; chips in the coach's welcome bubble, or typed natural language | not applicable (no pick to build) | N/A |
| One thread | no list at all; scroll chat up past the first bubble into dated dividers and folded summary cards | not applicable (no pick to build) | N/A |
| Seam strip | 22px always-on strip on the picture's bottom edge, accordions open over 240ms | not applicable (no pick to build) | N/A |

## 3. Settings and account

| element | spec value | build value | status |
|---|---|---|---|
| The app-level view | `settings-nested`: an iOS-Settings list where every row pushes its own full page with a back chevron | Nothing; the only second screen is the timeline list | MISSING |
| Entry point | the account avatar in the title row; no default click handler on the avatar, each surface wires its own | No avatar to tap | MISSING |
| Pane stack container | `.sn-stack` absolute, bottom 0, overflow hidden, top offset measured at runtime from the bottom of the title row | Absent | MISSING |
| Pane push / pop | `transform: translateX(100%)` to none, `.22s ease`; the pane beneath parallaxes to `translateX(-28%)`; teardown after 220ms | Absent | MISSING |
| Group / section | margin `14px 0 0`, background `--panel`, 1px `--line` top and bottom; header `500 13px mono`, uppercase, letter-spacing .06em, padding `0 16px 5px` | Absent | MISSING |
| Section header tracking | .06em here, .04em elsewhere, against the standard's flat +0.4 tracking | Absent | MISSING |
| Row (push type) | min-height 44px, padding `7px 16px`, border-top 1px `--line`; label max-width 52%, `13.5px Libre Franklin`; value right-aligned `13px mono` in `--f… | Absent | MISSING |
| Row label size | 13.5px against the binding 17/400 body floor | Absent | MISSING |
| Profile cell (root, top) | min-height 44px, padding `13px 16px`; face 48x48px circle, border `1.5px solid var(--data)`, `19px mono` initial or silhouette SVG; name `600 15px… | Absent | MISSING |
| Root list order | profile cell; group of Coach ("speak on" / "speak off") and Appearance (theme); group of Your diagrams (count) and Plan and licenses ("<n> licence(… | Absent | MISSING |
| Preferences content | first name, last name, birthdate; a way to sign out | Backend serves and accepts the three fields; no UI reads or writes them | MISSING |
| Preferences object fields | `speak`, `proactive`, `mode`, `theme`, `first_name`, `last_name`, `birthdate` | Backend present | PARTIAL |
| Account content | your diagrams (including the many-diagram professional case), licenses, beta plan and pricing, email and login method | Backend returns all five; no UI | MISSING |
| Profile page fields | First name, Last name, Birthdate (`type=date`), with the note "Your birthdate anchors your own line on the picture."; input row right-aligned `13.5… | Absent | MISSING |
| Speak-replies control, settings | a real iOS switch 51x31 inside a row of 44 or more, or a 24x24 checkbox with a 17px label in a 44 row. Never a native unsized checkbox | Absent | MISSING |
| Speak-replies checkbox as built | native checkbox 15x15px, `accent-color: var(--data)` | Absent | MISSING |
| Speak-replies row, chat view | min-height 44px, padding `6px 16px`, border-top 1px `--line`, label `500 17px mono` "speak replies", checkbox 24x24px `accent-color: var(--data)`;… | Absent | MISSING |
| Coach page | "Speak replies" switch; "Voice or text" segmented text/voice; "How often" segmented never/rarely/weekly; note "The coach never messages first unles… | Absent | MISSING |
| Segmented control | 32px high inside a 44 row, each segment 44px wide or more; `13px mono`, padding `4px 8px`, border 1px `--line`, adjoining segments `margin-left: -1… | `.seg` kept at 32px but only inside the event editor | PARTIAL |
| Appearance page | theme segmented: system, light, dark | Absent | MISSING |
| Diagrams page row | name `13.5px Libre Franklin`; sub `13px mono` = "N sessions · <when>"; `✓` tick in `--data` on the current diagram; row shows " · in use" when free | Absent | MISSING |
| Diagrams search threshold | search box appears at 6 or more diagrams (built), "more than about eight" (option prose), more than 8 (chat-first-app build) | Absent | MISSING |
| Plan and licenses page | badge `13px mono` border 1px `--data` radius 10px padding `3px 9px`; price `600 16px Libre Franklin`; manage button border 1px `--data` radius 14px… | Absent | MISSING |
| Sign-in page | Email row, Method row, "Sign out" posting to `/training/auth/logout` | Absent | MISSING |
| Sign out row | full width, centred, `13px mono`, colour `--ask`, min-height 44px, its own last group; no confirm dialog built | Absent | MISSING |
| No duplicate content | no surface repeats another surface's list; one home per setting. A second appearance is a named shortcut writing the same value | — | UNCHECKED |
| Switch as built (chat-first-app) | 51x31px, thumb 27x27px white circle, left 2px to 22px, `transition: left .15s ease` | Removed with the settings pages | MISSING |
| `avatar-popover` | floating popover `top:76px; right:10px; width:300px; max-height:470px`, radius 14px, shadow `0 10px 34px`, origin top right, `scale(.86)` to none `… | not applicable (superseded) | N/A |
| `account-page` | full-screen push from the right, `.24s ease`; profile face 46x46px; fixed 104px label column; full-width red sign-out | not applicable (superseded) | N/A |
| `right-drawer` | drawer ~85% width from the right; switch 38x22px; sheet radius `14px 14px 0 0`, `.2s ease` | not applicable (superseded) | N/A |
| `bottom-sheet-tabs` | sheet to 70% height, full state `calc(100% - 46px)`, radius `16px 16px 0 0`, `.24s ease` transform and `.2s ease` height; 22px grab handle | not applicable (superseded) | N/A |
| `picture-flip` | the picture area flips, `rotateY(90deg)` to none `.22s ease`, backface hidden; control pills `13px mono` radius 9px; 66px key column | not applicable (superseded) | N/A |
| `profile-card-first` | full page, opacity 0 to 1 `.2s ease`; card avatar 52x52px; name `800 21px Libre Franklin` 2-line clamp; 28x28px pencil button | not applicable (superseded) | N/A |
| `diagrams-first` | page slides up `.24s ease`; footer sheets max-height 74%, radius `14px 14px 0 0`; rows 56px with a 3px `--data` current bar | not applicable (superseded) | N/A |
| `you-conversation` | the chat thread swaps to a conversation about the user; inline switch 34x20px; diagram card list max-height 154px | not applicable (superseded) | N/A |
| `two-level-popover` | level 1 small popover, level 2 full push at `top:72px` `.22s ease`; face 30x30px; switch 38x21px | not applicable (superseded) | N/A |

## 4. Picture at rest — the sentence spotlight

| element | spec value | build value | status |
|---|---|---|---|
| The picture's place | above the chat, permanently on screen, editable | Pinned above the chat, always on | MET |
| The picture's nature | an utterance, never a workspace. No legends, no filter UI, no selection furniture. The system decides what matters and shows it | No legends, no filter interface, no selection furniture | MET |
| Detail level | cartoon-level, strip-small, one or two lanes; surface one or two correlations, never a dataset | One wire, cartoon scale | MET |
| Chosen chapter view | sentence spotlight: the coach's message lights the events it names, the rest stay dim dots, up to three rows of words tied to their dots by leader… | Sentence spotlight drives the picture from the coach's latest message | MET |
| Level heights | resting wire 78px, chapter 158px, moves board 264px. A different height is allowed only if the proposal states what chat area it gives up | One height, 158, growing to 252 while a move is on stage | CHANGED |
| Picture container | `.pic` position relative, border-bottom 1px `--line`, padding `4px 10px 8px`, background `--panel` | — | UNCHECKED |
| View height transition | `transition: height .25s ease` (.24s as built in chat-first-app) | — | UNCHECKED |
| Picture height stability | the picture is pinned at its level's height by both its wrapper (`height:158px; flex:none`) and its viewBox, so nothing below it moves | The same container swaps between 158 and 252 whenever a move goes on stage, so a chip tap resizes the picture and shoves the chat down | CHANGED |
| Caption slot | `font-size:13px; margin-top:4px; min-height:15px`, colour `--faint`, padding `0 4px` | The caption element is toggled with hidden, so it leaves and re-enters the layout on every selection; its CSS has no min-height | CHANGED |
| Caption strip, scaffold variant | 11.5px `--faint`, min-height 15px | not applicable (superseded) | N/A |
| Resting wire height | 78px, viewBox `0 0 380 78`, x0=16, x1=364 | No separate resting level; the chapter picture is the only level | CHANGED |
| Baseline | `<line x1=16 y1=46 x2=364 y2=46 stroke="var(--line)" stroke-width="1.5">` | Wire drawn at y=99 per the chapter geometry | MET |
| Chapter box | `<rect y=12 height=52 rx=8 fill="var(--data)" opacity="0.07">` plus an outline rect `fill=none stroke="var(--data)" stroke-width=1 opacity=0.35` ca… | No cluster body is drawn; a bracket marks the focus | CHANGED |
| Chapter box pulse | opacity `.35 → 1 → .35`, `2.2s ease-in-out infinite`; disabled under reduced motion | No chapter box to pulse | MISSING |
| Sparse chapter dots | one `<circle r="4.5" fill="var(--data)">` per moment, evenly spaced across the box | Dots at the ratified radii | MET |
| Dense chapter glyph | more than 8 moments collapse to `<circle r="11" stroke="var(--data)" stroke-width="1.6">` with a count text at font-size 10 | Count pills were removed in favour of density-scaled dots | CHANGED |
| Count text size | 9-10.5px against the binding 13px floor | No count text | MISSING |
| Chapter year-range label | `<text y=26 font-size="10.5" fill="var(--faint)">` two-digit years | Years at the two ends at 13px | MET |
| Gap question mark | `<text font-size="13" fill="var(--ask)">?</text>`, shown only when the gap between chapters is 4 years or more | One amber question mark past the end of the wire | MET |
| Hint text | `<text x=16 y=74 font-size="9" fill="var(--faint)">tap a chapter</text>` | — | UNCHECKED |
| Empty-record copy | "Nothing on your line yet — it draws itself as you talk.", `font-size:13px; color:var(--faint); padding:10px 6px` | — | UNCHECKED |
| Empty wire, as built FD-362 | dashed line `stroke-dasharray: 3 6` plus a centred "?" | Dashed line plus a centred question mark | MET |
| At-strip-scale vocabulary | exactly three marks: a line, dots, and the amber question mark. Bands, ranges, fades and ticks belong to the expanded view only | The wire, dots and one amber question mark; no fades or ticks. A span band is drawn when the coach asks for a span view | PARTIAL |
| Every mark speaks | a plain sentence on tap, e.g. "sleep got worse, around 1996, give or take a year". No legends anywhere | A tap writes the moment over three rows: when, who, and its own words | MET |
| No progress bar | no data-completeness bar, no notion of being finished; the readout shows what more data buys, as specific answerable questions | None | MET |
| Questionnaire register | rejected; conversation drives everything and the picture is only a secondary way to fill gaps | None | MET |
| Lane filter buttons | rejected; hiding lanes by hand is "a data project no one wants" | None | MET |
| Click-to-filter or select people | rejected, same reason | None | MET |
| Lanes | conversation-aimed pairs chosen by the coach or by user pins, never an always-on grid, never a filter UI | No lanes; one wire | MET |
| The lane-design round | the whole round rejected as clunky and uncommunicative | not applicable (superseded) | N/A |
| Clusters | central and kept; the valuable thing to show, an innovation for Bowen theory from this app's timeline data | Model-derived and stored | MET |
| Bands | good but data-gated: each captured span earns a band; dated relationship spans barely exist outside the hand-curated case, so they are a coach elic… | A filled span band at 14% opacity is drawn when the coach asks for a span view; no data-gated relationship bands | PARTIAL |
| The FD-360 expanded picture | rejected: boxes scattered in lanes too sparse to read as a common timeline, question-mark tags irregularly placed | not applicable (superseded) | N/A |
| Green boxes, blue-dot-and-bar boxes, white vertical and dashed lines | rejected as unreadable without labels, with no room for labels | not applicable (superseded) | N/A |
| Horizontal timeline scrolling | required, with pan and zoom that handle irregular spans without dead space | No pan or zoom; one wire fits the chapter | CHANGED |
| Chapter view geometry (level 2) | height 158, viewBox `0 0 W 158`, x0=16, x1=W-16 (W = phone client width, default 378); wire at y=99; year labels at top 136; label rows at y 44 / 5… | Exactly those constants | MET |
| Chapter wire line | `<line y1=99 y2=99 stroke="var(--line)" stroke-width="1.5">` | MET | MET |
| Dot density rule | base radius by count: 12 or fewer = 4.5; 30 or fewer = 3.5; 60 or fewer = 2.6; above that = 1.8 | Exactly those radii | MET |
| Base dot opacity | 0.35 once anything is lit; otherwise 1 when the chapter holds 24 or fewer moments, 0.6 above that | Exactly that rule | MET |
| Plain dot | `<circle cy=99 r=r0 fill="var(--data)" opacity=baseOp>` | MET | MET |
| Lit ordinary moment | `<circle r="5" fill="var(--data)">` at its stacked y | MET | MET |
| Selected moment dot | `<circle r="7" fill="var(--data)">` at full opacity; selection overrides the nodal rendering | MET | MET |
| Shared-date cluster ring | `<circle r="7" fill="none" stroke="var(--data)" stroke-width="1" opacity=baseOp>`, once per date group holding more than one moment; opacity 0.35 w… | MET | MET |
| Lit-dot stacking | same date, multiple lit: y = 104 for the first when more than one is lit (else 99), 94 for the second, then `104 + 10*(i-1)`. Up to three stacked o… | MET | MET |
| Leader line | `<line y1=99 y2=ROWS[i]+15 stroke="var(--data)" stroke-width="1" opacity="0.5">`, one per unique x, labels sorted by x and sliced to three, deduped… | Sorted, sliced to three, deduped on the rounded x, 1px var(--data) at 0.5 opacity, none in the selected writeout | MET |
| Label row text | `400 13px/15px "IBM Plex Mono"`, colour `--ink`, height 15px; lit rows `color: var(--data); font-weight: 500`; meta rows `color: var(--faint)` | MET | MET |
| Label placement and budget | up to 3 rows; horizontal budget `min(44, floor((x1 - x - 4) / 7.8))` characters, left-aligned right of its dot; under 12 characters it flips to rig… | The build skips both the label and its leader when the remaining width is under one character, so a crowded picture loses leaders the mockup would still draw | CHANGED |
| Year labels | `400 13px/17px "IBM Plex Mono"`, colour `--faint`, at top 136px, left edge and, if different, right edge | MET | MET |
| Which moments light | the most recent coach bubble's chips carry `data-mo` with the event indices they name; those light. A chapter of 3 or fewer lights all; otherwise i… | MET | MET |
| Selected-moment writeout | replaces the spotlight rows: row 0 is meta (`date · who`, faint), rows 1 and 2 are the wrapped label; wrap width `floor((x1-x0)/7.8)` characters pe… | MET | MET |
| Word-row format | `{dateText} · {who, if not the protagonist} · {label}`; date is the year alone when the fraction is under 0.002, else `Mon YYYY` | A guessed date says its year only, a certain one says the month | MET |
| Undated shelf | undated items sit below the lanes and are never positioned; they exist, undated | A question mark past the end of the wire; nothing undated is drawn on the line | MET |
| Undated shelf visibility | visible at the panel base, or behind a tap | not applicable (no pick to build) | N/A |
| Undated shelf chip | dashed border 1px `--unsure`, border-radius 7px, padding `6px 9px`; the row masked with `linear-gradient(90deg,#000 82%,transparent)` at the right… | Caption offers Ask when on the shelf | PARTIAL |
| Full-picture escape hatch | header "‹ THE WHOLE PICTURE", range label "1990 — TODAY", hint "pinch · drag", hint "hold any mark to fix it", undated shelf peeking from the base | not applicable (no pick to build) | N/A |
| Freshness banner copy | extracting: "Updating the picture from your conversation…"; pending review: "New details from your conversation are waiting to be added."; chat ahe… | Unchanged from the earlier branches | MET |
| Pin label row, FD-362 | "Family time line" at the left, mono 13px uppercase, tracking .08em; the right span carries the picture's state text | Present | MET |

## 5. Picture symbols — one row per symbol

| element | spec value | build value | status |
|---|---|---|---|
| Person, female | `<circle r="13" fill="var(--panel)" stroke=currentColor stroke-width="1.5">`, rising to 2.4 when a move overrides the stroke | Everyone is a circle r17 stroked var(--faint) at 1.6; sex is never drawn | CHANGED |
| Person, male or other | `<rect width="24" height="24">` offset -12/-12, same fill and stroke rules | Everyone is a circle r17; no rect | CHANGED |
| Person, play-by-play pane A | disc r=17, fill `--card`, stroke `--mute` 1.6; initial `600 12px "IBM Plex Sans"` centred; name mono 9px `--mute`, letter-spacing .04em, at y = cy… | People appear only while a move plays | MISSING |
| Person name label, board | `<text y="-20" font-size="10.5">`, fill `--move` and weight 600 for the current mover, `--faint` and 400 otherwise | Stage names raised off 11px to the 13px floor | MET |
| Emotional field, rings | three `<circle cx cy r=24 fill=none class="A d" stroke-width="2.4" opacity="0">`, `r` animating 18 to 170 over 1.65s, begins staggered at 0s / .55s… | Two static circles at radius 25 and 33, stroke-width 1.2, opacity 0.4; nothing pulses | CHANGED |
| Tremble | `@keyframes tremble10`, ±2.5px falling to ±2px, active 2-28% of a 10s loop, still afterwards | Distance marks the actor still from the first frame; no exposed-then-sheltered beat | MISSING |
| Wall | thick line `x1=105 y1=30 x2=105 y2=98`, `.A d`, stroke-width 6; `@keyframes oneslabb` slides it in from `translateX(-48px)` with opacity 0 to 1 bet… | A plain 52px line stroked var(--ink) at 4 | CHANGED |
| Field shadow behind the wall | a per-instance `clipPath` with `clip-rule="evenodd"`, a rect minus an angled wedge (`M0 0 H230 V130 H0 Z M105 30 L105 98 L0 142 L0 -14 Z`), applied… | No clip path; the field rings are complete circles passing straight through the wall | MISSING |
| Pre-wall / post-wall gating | `@keyframes preA` opacity 1 to 0 by 26-30%; `@keyframes postA` opacity 0 to 1 rising at 38-42%; both 10s infinite | No pre and post phases | MISSING |
| Authorship trace | dashed line `x1=57 y1=64 x2=102 y2=64`, `.A d`, stroke-width 1.6, `stroke-dasharray="3 5"`, opacity animating `0;0;.55;.55` on keyTimes `0;.4;.46;1… | — | UNCHECKED |
| Distance | the wall drawing, alone | Wall drawn, but static and in ink rather than green | CHANGED |
| Cutoff strike-through | `x1=92 y1=86 x2=118 y2=42`, `.A d`, stroke-width 3, gated by `postA` on a 10s loop | Strike drawn stroked var(--ink) at 2 rather than the move green | CHANGED |
| Conflict, both figures | mover circle `cx=45 cy=55 r=14` `.A` with `buzz .28s infinite`; target rect `x=162 y=41 w=28 h=28` `.A` with `buzz .28s infinite reverse` | Both figures shake, which is right | MET |
| Conflict, sparks | one zigzag polyline `points="70,55 82,48 92,62 102,49 112,61 122,49 132,61 144,55"`, `.A d`, stroke-width 2.4; plus an 8-line radial spark cluster… | Four small parallel zigzags stacked 9px apart at the midpoint, no radiating sparks, no scale pulse | PARTIAL |
| Toward, the walk | mover circle `cx=45 cy=55 r=14` `.A`, `@keyframes slide` translateX 0 to 96px at 50%, held to 94%, `8s ease-in-out infinite` | The actor advances 9px along the line | PARTIAL |
| Toward, the arrow | line `y1=55 x2=146 y2=55` `.A d` stroke-width 2.4 `stroke-dasharray="10 8"`, `flow 1s linear infinite`; nested `<animate>` on `x1` with values `62;… | The arrow draws once over 0.6s and stays drawn; the tail does not travel | PARTIAL |
| Away | mirror of toward: mover `cx=120 cy=60 r=14`, `awaywalk` translateX 0 to -68px between 50% and 94% over 8s; trailing line `.A d` stroke-width 2.4 `d… | The arrow draws over 0.6s and then stays on screen for good | PARTIAL |
| Projection, blur | `<filter id="pb" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="1.2"/></filter>` | Blur present | MET |
| Projection, sharp selves | parent `cx=52 cy=50 r=15` `.A` stroke-width 2; child `cx=178 cy=92 r=11` `.A` stroke-width 2 | Present | MET |
| Projection, ghost-double | the same circle inside the blur filter, `.A d` stroke-width 2, with `pshakeC 1.1s infinite`; parent opacity `1;1;0;0` and child opacity `0;0;1;1`,… | Ghost and shake are right | MET |
| Projection, spike static | 8 lines `.A d` stroke-width 1.8, each with its own opacity flicker between 0.27s and 0.58s; the group scaling `1;1;.12;.12` on the parent and `.12;… | Identical full spike sets on both people at once at stroke-width 1.6, with no inverse gradient | CHANGED |
| Projection, flow arrow | `x1=68 y1=57 x2=156 y2=83` `.A d` stroke-width 2.8 `stroke-dasharray="9 7"`, `flow .45s linear infinite`; head `<polygon points="165,86 150,76 153,… | stroke-width 2.4, dasharray 6 6, drain 1.4s | CHANGED |
| Anxiety shake primitive | `pshakeC` / `cshakeC`, identical: `0%,100%(0,0) 20%(-2.5,1.5) 45%(2.5,-1.5) 70%(-2,1) 85%(2,-1)`, 1.1s infinite | Present | MET |
| Anxiety variable | the projection rig on a single figure: sharp base `cx=115 cy=64 r=17` `.A` stroke-width 2.2 always present; ghost-double with its own blur filter a… | The standalone anxiety shift also draws the two-ring emotional field that belongs to distance and cutoff | CHANGED |
| Overfunctioning | dominant circle `cx=88 cy=64 r=15` `.A`, `domup 3s ease-in-out infinite` translateY 0 to -5px; UP flank arrow shaft `x1=60 y1=76 x2=60 y2=54` plus… | Flank arrow only at stroke-width 2.2, 22px against a 34px person; nobody rises | PARTIAL |
| Underfunctioning | submissive rect `x=128 y=50 w=28 h=28` `.A`, `subdown 3s ease-in-out infinite` translateY 0 to +5px on the same beat, opposite phase; DOWN flank ar… | Flank arrow only; nobody sinks | PARTIAL |
| Flank arrow size | shaft about 22px against a 15-17px main-mark radius, which reads as ~60% size. Reduced to half or two-thirds of the first attempt | 22px against a 34px person | PARTIAL |
| Triangle, inside | target rect `x=118 y=36 w=26 h=26` static; mover circle r=13 with `cx` `100;100;58;58` and `cy` `49;49;56;56` on keyTimes `0;.2;.55;1` over 8s; dis… | The actor advances 14px and never overlaps; the third person is pushed out, which is right | PARTIAL |
| Triangle, outside | two static corners: circle `cx=88 cy=40 r=13`, rect `x=128 y=27 w=26 h=26`; two tension zigzags `points="104,84 100,76 106,68 98,60 103,52"` `.A d`… | — | UNCHECKED |
| Fusion | person A circle `cy=64 r=15` with `cx` `70;70;101;101`; person B rect `y=50 w=28 h=28` with `x` `140;140;112;112`, both on keyTimes `0;.2;.55;1` ov… | Three fixed concentric ellipses around the pair's midpoint at stroke-width 1.4, opacity 0.6; nobody approaches, nothing shrinks, no shared field | CHANGED |
| Defined self, actor | circle `cx=42 cy=64 r=15`; ink phase `.A` stroke-width 2.2 with opacity `1;1;0;0` at keyTimes `0;.375;.385;1`; green phase, same geometry, `stroke=… | Green from the first frame | CHANGED |
| Defined self, the storm | other party rect `x=172 y=50 w=28 h=28` with `btrem2 12s infinite`; two long storm rings `r` 18 to 170 over 1.1s (second `begin=".55s"`), opacity `… | No storm at all | MISSING |
| Defined self, clear ring | `cx=42 cy=64 r=20 stroke="var(--self)" stroke-width="2.4" opacity="0"`, `r` 18 to 120 over 2s, `begin="3.2s;11.2s"`, opacity `.95;0` | One static ring at r=R+12, stroke-width 1.6, opacity 0.7 | CHANGED |
| Symptom cross | `translate(146,60)` with two `<rect class="df" rx="1">`, `x=-8 y=-3 w=16 h=6` and `x=-3 y=-8 w=6 h=16`, filled solid green | A filled disc r9 in var(--panel) with a green 2px ring carrying a thin 8px plus; it reads as a badge, not the ratified cross | CHANGED |
| Symptom up arrow (worse) | shaft `x1=172 y1=74 x2=172 y2=48`, head `<polygon points="172,42 164,52 180,52" class="df">`; opacity `0;0;1;1;0;0` on keyTimes `0;.08;.14;.48;.54;… | A separate chevron at stroke-width 2 | CHANGED |
| Symptom down arrow (better) | shaft `x1=172 y1=48 x2=172 y2=74`, head `<polygon points="172,80 164,70 180,70" class="df">`; opacity keyTimes `0;.5;.56;.9;.96;1`, visible 56-90% | A separate chevron at stroke-width 2 | CHANGED |
| Functioning | one circle `cx=115 cy=64 r=17 fill=none stroke-width="2.6"`; `stroke-dasharray` animating `106 0; 106 0; 5 6; 5 6; 106 0; 106 0` on keyTimes `0;.12… | Drawn as a node ring state rather than one dash-morphing outline | CHANGED |
| Nodal moment mark | double ring: `<circle r="6.5" fill="none" stroke="var(--data)" stroke-width="1.5">` plus a solid `<circle r="2" fill="var(--data)">` core | Exactly that | MET |
| Anxiety spikes, generic generator | `gSpikes`: stroke-width 1.6, opacity animating `0;1;.2;1;0` over 0.3-0.75s staggered per spike, n spikes between radius r+2 and r+2+l where l = 6 +… | Replaced by moves.ts and the .mv-* classes | CHANGED |
| Directed arrow, generic generator | `gArrow`: dashed line stroke-width 2.4, `stroke-dasharray: 8 6`, `gflow .5s linear infinite`; polygon head; optional ride translate over 1.2s with… | Replaced by moves.ts | CHANGED |
| Conflict zigzag, generic generator | `gZig`: polyline stroke-width 2.2, segment count `max(4, round(L/13))`, `gsparkp .5s infinite` scaling .75 to 1.1 | Replaced by moves.ts | CHANGED |
| Wall, generic generator | `gWallPair` / `gWallSolo`: wall bar stroke-width 4.5 paired or 4 solo; ripple circles stroke-width 2 animating r 16 to L*0.9 over 1.5s, the second… | Replaced by moves.ts | CHANGED |
| Fusion, generic generator | `gFusion`: three parallel lines at y = -6, 0, 6, stroke-width 2.4 | Replaced by moves.ts | CHANGED |
| Ring, generic generator | `gRing`: stroke-width 2.2, r animating `16;16;80;80` over 8s, opacity `0;.9;0;0`, `begin=".8s"` | Replaced by moves.ts | CHANGED |
| Flank, generic generator | `gFlank`: two lines forming a chevron, stroke-width 2.2, `animateTransform` bobbing `4*sign` over 3s infinite | Replaced by moves.ts | CHANGED |
| Move colour | one green for every move mark, `--move` / `MV` | The wall is var(--ink) at 4 and the cutoff strike var(--ink) at 2, not the one green | CHANGED |
| Symbol legibility rule | symbols must be self-evident without a legend, and each move must be apparent in the drawing itself. A text label is not enough; cutoff must show w… | — | UNCHECKED |
| Symptom badge, playbyplay variant | circle r=7.5 offset (+14,-14), fill `--amber-line`; "!" `700 10px "IBM Plex Sans"` fill `#1a1200`; `pop .5s cubic-bezier(.2,1.6,.4,1)` scale .2 to 1 | not applicable (conflict with no pick) | N/A |
| Anxiety ring, playbyplay variant | two concentric rings at r = R+7 = 24, stroke `--amber-line` 2.2 opacity .85, `pulse 1s ease-out` twice, scale .75 to 1.35, opacity 1 to .15 | not applicable (conflict with no pick) | N/A |
| Cutoff, playbyplay variant | `.cutline` stroke `--mute` 1.6 round cap drawn over 500ms; after 480ms two 8px diagonal slash ticks stroke `--ink` 2.2 pop in at the midpoint ±4px;… | not applicable (conflict with no pick) | N/A |
| Drawability tick | `.tick` stroke `--ink` 1.5-2px; a moment with no direction | Not drawn; belongs to the expanded view, which is not built | MISSING |
| Drawability dot | `.dot` fill `--draw`, r 3.2px; a directed moment, up or down | Dots are drawn on the wire | MET |
| Step line | `.step` stroke `--draw` 2.2, round cap; drawn only when the directed-point threshold is met, spanning only where points exist | No lines; belongs to the expanded view, which is not built | MISSING |
| Uncertainty band | `.band` fill `rgba(201,148,65,.30)` light / `rgba(216,168,83,.26)` dark; zoomed or secondary `.bandZ` at .20-.22 | The words say the guess; no band is drawn | MISSING |
| Gap / silence | dotted line, stroke `--muted` 1.6, `stroke-dasharray: 1.5 5`, opacity .55 | Not drawn; belongs to the expanded view | MISSING |
| Recorded no-change | `.flat` stroke `--ink` 2.5, round cap | Not drawn; belongs to the expanded view | MISSING |
| Open-ended range fade | gradient stops, stop-opacity .5 to 0, colour `--draw` | Not drawn; belongs to the expanded view | MISSING |
| Ordering between guesses | order is drawn only when the guess ranges do not touch (1994±1 against 1996±1 draws it; two "1992" guesses sit side by side with none) | Not drawn; belongs to the expanded view | MISSING |
| Amber question glyph | 13x13px circle, border `1.3px solid var(--unsure)`, `500 9px mono`; `@keyframes ask` opacity .55 to 1, 2.8s ease-in-out infinite; off under reduced… | Mono 15px, 13px when small, filled var(--ask); not the 13x13 outlined circle | CHANGED |
| Trace highlight on a bubble | `outline: 2px solid var(--move)`, offset 2px, `tracefade 2.2s ease-out forwards`, holding solid through 40% then fading to transparent | Removed | MISSING |
| Abstract people-mapping | rejected. If the visual maps people it IS the family diagram, or a subset showing the movement between people: Bowen's chalkboard, sequence on the… | No abstract people map | MET |
| Chapter Shelf list-row glyph set | compact glyphs: vertical tick plus circle for single-actor moves; bowing polylines for toward and away; one zigzag for conflict; two segments with… | not applicable (no pick to build) | N/A |

## 6. Chalkboard / moves board

| element | spec value | build value | status |
|---|---|---|---|
| The three levels | resting wire 78px → chapter 158px → moves board 264px, one continuous zoom, one visual language; the claims live in chat | One level only | CHANGED |
| The middle level, tap-zoom cluster | CUT. Tapping a cluster is point-and-ask; the cluster's words live in the chat via the play-by-play, never in a navigable data view. The move step-t… | Correctly absent | MET |
| Board height, phone | 264px, viewBox `0 0 380 264` | Stage height 252, not 264 | CHANGED |
| Board layout, phone | centre (190,132); people on a ring of radius R=82, angle `-π/2 + i*2π/n`, x radius `R*1.75` and y radius `R` | Ring radius min(78, max(46, width/2-74)) flattened to 0.62 vertically | CHANGED |
| Board layout, desktop original | viewBox `0 0 840 290`, centre (420,145), ellipse radius 180 across by 100 down, ordered by bond adjacency | not applicable (no pick to build) | N/A |
| Pair-bond lines | stroke `--line`, stroke-width 1.2, drawn first, beneath everything | None | MISSING |
| History marks | earlier moves stay on the board at `opacity: 0.16`, behind the current gesture; they fade in over `.32s ease` from 0 | None | MISSING |
| Gesture glow filter | `<filter><feGaussianBlur stdDeviation="1.1"/></filter>` | — | UNCHECKED |
| Current-mover emphasis | mover label fill `--move`, weight 600; every other label fill `--faint`, weight 400 | — | UNCHECKED |
| Board nav, back | `←` in the top-left corner slot | No board, no back control | MISSING |
| Cluster-view close | `✕` in the top-right corner slot at level 2 | No cluster level to close | MISSING |
| Board step controls | `◀` plain `.btn` and `▶ next move` `.btn.primary`, min-height 44px, padding `0 14px`, border-radius 4px | No step number, no back or next control, no way to hold on one move | MISSING |
| Board entry button | `▶ watch the N moves`, `.btn.primary` with `border-color: var(--data); color: var(--data)`; base `.btn` is `500 12px "IBM Plex Mono"`, padding `6px… | A plain Play button in the caption row instead of "watch the N moves" | CHANGED |
| Board caption | `13px`, min-height 15px (20px in drilldown), reading `step/total · year — from → to · label`, plus a trace chip back to the coded chat message | No playback caption | MISSING |
| Zoom into a chapter | SVG `transform: scale(min(4, viewBoxWidth/boxWidth))`, `transition: transform .6s cubic-bezier(.4,0,.2,1), opacity .6s`, opacity to 0.25, level swa… | No level to zoom into | MISSING |
| Vertical space | too much is wasted in the zoomed-out timeline and the zoomed-in cluster views. Only the play-by-play may expand, because it is graphics-rich | — | UNCHECKED |
| The crowded chapter view | rejected on font size and label collision in dense clusters; surgical fixes will not do, the view needs rethinking | Correctly absent | MET |
| The chalkboard replaces the heat map | numbered moves on a subset of the full diagram, one tap from the wire | No heat map, and no chalkboard level either | PARTIAL |
| Episode-open lanes | two lanes only, the subject's plus the one the correlation needs; amber threads tie correlated moments; an uncertainty band ends where a question r… | Not built | MISSING |
| Wire at rest, composite | viewBox `0 0 760 70`; caption "Three episodes, one count chip, one amber question. Nothing else until you ask." | The one wire | MET |
| Chalkboard, composite | viewBox `0 0 760 150`; numbered moves on the diagram subset | Not built as a level | MISSING |
| Pairs, face to face | two moments side by side, a question mark between them, no axis | The compare view simply spotlights both moments | MISSING |
| Bands under the wire | quiet horizontal bands beneath the main wire, start and end dated, ending where dots pile up | Not built | MISSING |
| Braid, two rails | two parallel rails, self and other, with correlation ties | not applicable (superseded) | N/A |
| Constellation / Chapters | named episode groupings, no axis in the Chapters variant; drift rightward through years in Constellation | Clusters name themselves | PARTIAL |
| Other divergent picture concepts | comic strip, tree rings, one bond one thread, words sized by frequency, year wheel, mobile, story spine, seismograph, question horizon, walked path | not applicable (no pick to build) | N/A |
| Close-up triangle drawings and cluster vignettes | explicitly LATER | Correctly deferred | MET |
| Section numbering in mockups | sections and boxes in mockups must be numbered so they are easy to refer to | — | UNCHECKED |

## 7. Show-tool view kinds

| element | spec value | build value | status |
|---|---|---|---|
| `triangle` — a triangle over three people | no mockup fixes the geometry | Wired end to end; the page puts that cast on stage but draws the same plain circular ring, not a triangle figure | PARTIAL |
| `span` — a span over a time range | no ruled drawing; the as-built draws a filled band at 14% opacity | Wired; draws a filled band at 14% opacity | PARTIAL |
| `compare` — two moments compared | no mockup. The nearest approved drawing is "Pairs, face to face": two moments side by side, a question mark between them, no axis | Wired, but it simply spotlights both; nothing draws the comparison | PARTIAL |
| `sequence` — a sequence of moves | the moves board, stepped in order | Wired, stepping each move on a fixed 1100ms beat, with no step controls | PARTIAL |
| `cluster` — a cluster view | not in the ruled starting set of four | Shipped, beyond the ruled starting set of four | CHANGED |
| Parameter validation | missing parameters raise by name; every person and event id is checked against the record before a view is built | Missing parameters raise by name; every person and event id is checked against the record before a view is built | MET |
| Extensibility | adding a kind must be easy; each kind added must show something meaningful | Adding a kind takes three files across two languages and nothing fails a build if one is forgotten | PARTIAL |

## 8. Play-by-play

| element | spec value | build value | status |
|---|---|---|---|
| Authorship | coach-authored: the moves are data and animate deterministically; the coach writes the words around them, picks which moves and in what order, make… | The play endpoint returns a coach-written statement whose chips step the picture, so the authoring half is right; the surface it should be drawn on is missing | PARTIAL |
| Priority | the play-by-play is where the value is. Fix timing and symbol gaps before adding anything; close-up triangles and eventually the family diagram com… | — | UNCHECKED |
| Owner's verdict on the coded version | "looks and feels great, that is what I wanted" | — | UNCHECKED |
| Pinned picture region | background `--card2`, border-bottom 1px `--rule`, padding `10px 12px 4px`. A FIXED region above the chat | The picture region resizes from 158 to 252 while a move plays | CHANGED |
| Picture SVG | `viewBox="0 0 440 262"`, `width:100%; height:auto` | Not the pane A stage | MISSING |
| People on stage | five people permanently on stage at fixed coordinates, disc r=17, 12px initial, 9px mono name 30px below | People are drawn only while a move plays; the axis and the people are never on screen together | MISSING |
| Time axis | stroke `--rule` 1.4, full width at y=222 from x=30 to x=424; ticks at 1985, 1995, 2005, 2015, 2025; year labels `"IBM Plex Mono"` 9px fill `--mute` | Not drawn with the people | MISSING |
| Density blobs | ellipses at three points, rx `[6,10,7]`, ry = rx × 0.68, fill `--idle` | Not drawn | MISSING |
| Focus blob | fill `--teal` at opacity .28, rx=27 ry=9; `.flash` at opacity .6 reverting after 900ms | Not drawn | MISSING |
| Move dots on the axis | r=3.4 fill `--idle`; once played, r=4.6 fill `--teal`, `transition: fill .3s, r .3s`; `.flash` fill `--amber` | Not drawn | MISSING |
| Cluster bracket and label | bracket stroke `--teal` 1.2; label mono 9px fill `--teal-ink`, letter-spacing .04em, e.g. "1993–1997" | The bracket path is drawn with no label | PARTIAL |
| Node move transition | `transition: transform .55s cubic-bezier(.4,1.3,.5,1)` — an overshoot ease | A move moves the person as geometry, not as a pulse | MET |
| Node pop-in | `@keyframes pop` scale .2 to 1, opacity 0 to 1, `.5s cubic-bezier(.2,1.6,.4,1)` | — | UNCHECKED |
| Move arrow | `fill:none; stroke:var(--teal); stroke-width:2.4; stroke-linecap:round`; drawn in over 600ms ease-out; arrowhead marker `viewBox="0 0 10 10" refX="… | Drawn once over 0.6s and left on screen | PARTIAL |
| Chat log region | padding 14px, flex column, gap 11px, min-height 214px — the GROWING region below the fixed picture | The chat fills what is left and is the only thing that scrolls | MET |
| Coach typing speed | 2 characters then an 18ms sleep, about 9ms per character; the closing ask line at 16ms per 2 characters | — | UNCHECKED |
| Per-move narration hold | 1000ms after each chip or move before the prose continues | Each step is 1.1s | CHANGED |
| Offer-chip stagger | 160ms between each of the three answer chips | — | UNCHECKED |
| Initial coach delay | 320ms before typing starts, 260ms before the ask line | 300ms before the first-run greeting types | PARTIAL |
| Typing caret | 2px by 1em bar, background `--teal`, `@keyframes blink .7s steps(1) infinite` | Three bouncing dots plus a 2px blinking cursor | CHANGED |
| Ask prompt line | `margin-top: 9px`, colour `--amber`, weight 500 | The page draws offered chips, but the live coach does not write them yet | PARTIAL |
| Composer field, play-by-play | min-height 34px, border 1px `--rule`, radius 10px, padding `7px 10px`, font-size 13.5px, background `--card2`; focus `outline: 2px solid var(--teal)` | A contenteditable composer, min-height 44, max-height 140 | CHANGED |
| Send affordance, play-by-play | mono 11px, letter-spacing .09em, colour `--mute`, uppercase — plain text, not a button graphic | A 44x44 circular send button | CHANGED |
| Beat length, as built | 1400ms in chat-first-app, 1100ms in FD-362 | 1100ms per move against the ruled 8s story loop | CHANGED |
| Chip lights while its move draws | `LIT_MS = 1000` | LIT_MS 1000; the chip lights amber while its move draws | MET |
| Play triggers a fresh coach turn | `playThrough(clusterId)` calls the play endpoint, types the reply, and steps the picture per named event | Present | MET |
| Pane B, app-generated record | tape region border-bottom 1px `--rule`, background `--card`, padding `11px 13px 13px`, mono 12px, min-height 132px; header 9.5px uppercase; one fla… | Correctly absent | MET |

## 9. Chips

| element | spec value | build value | status |
|---|---|---|---|
| Chips are the primitive | a chip is a reference into the record — an event, a cluster or a person — rendered in both coach and user messages | Chips render in coach messages and drop their words into the composer | MET |
| Two taps on the picture | the first tap looks: a title or caption, free, nothing enters the chat. The second tap is a chip and speaks | Taps look, chips speak, and only a coach turn or Play draws | MET |
| Coach-placed inline chips | tappable chips inside coach prose that jump to a cluster or a set of events | The coach's chips aim the picture | MET |
| Base chip, converged files | `display:inline-block; font:500 13px "IBM Plex Mono"; color:var(--data); border:1px solid var(--data); border-radius:10px; padding:1px 8px; margin:… | mono 500 13px/22px, radius 13, padding 1px 10px, no border by default, target grown by a ::before inset | CHANGED |
| Base chip, earlier files | the same shape at `500 11px mono` | not applicable (superseded) | N/A |
| Chip data attributes | `data-aim="{chapterIndex}" data-mo="{comma-separated event indices}"` | — | UNCHECKED |
| Chip markup, server side | `[[kind:target\ | Parsed server-side, unresolvable references dropped | MET |
| Chip payload by kind | chapter → `cluster_id`; events → `event_ids`; person → `person_id`; range → `start` and `end` as ISO dates | — | UNCHECKED |
| Trace chip ("coded in") | `.chip` reading `coded in: <title, truncated at 30 chars> · <short date> →`, carrying `data-sid` and `data-bi` | No coded-in chip anywhere | MISSING |
| Data chip, play-by-play | `font:500 12.5px/1.25 "IBM Plex Sans"; display:inline; padding:2px 8px; border-radius:999px; background:var(--teal-soft); color:var(--teal-ink); bo… | Teal-bordered .data tone rather than a filled teal pill | CHANGED |
| Lit chip | background `--amber-soft`, colour `--amber`, inset ring `--amber-line` | Amber text and border on --ask-tint | MET |
| Offer / ask chip | `background:transparent; color:var(--amber); box-shadow: inset 0 0 0 1px var(--amber-line); border-radius:8px; font:"IBM Plex Mono" 11.5px; padding… | Amber border, radius 8, literal square brackets, no background; the live coach does not emit them yet | PARTIAL |
| Token pill in the composer | `font:"IBM Plex Mono" 11.5px; background:var(--amber-soft); color:var(--amber); box-shadow: inset 0 0 0 1px var(--amber-line); border-radius:6px; p… | Tapping an offered chip puts its words in the message | MET |
| Chip inside a user bubble | `color: var(--onaccent); border-color: currentColor` | color var(--onaccent), border-color currentColor | MET |
| Chip height | the as-built chips are 26px tall, under the 44px tap floor; the approved mockup draws them at about 21px. A 44px target inside flowing prose cannot… | 26px visual with the target grown to 44 by a ::before inset | MET |
| Chip clip then fire | an over-long label shows clipped with an ellipsis; the first tap un-clips it, the second fires | Present | MET |
| Chip tones, as built | `.data` teal border; `.ask` amber border, radius 8, literal square brackets, no background; `.lit` amber text and border on `--ask-tint` | Present | MET |
| Historical coach messages | carry no chips; references only come back on a live reply | — | UNCHECKED |
| Count chip | opens on tap to reveal a dense episode's contents | Count pills were removed in favour of density-scaled dots; no tappable count chip | CHANGED |
| Inline links instead of chips | `.ilink` colour `--draw`, dotted underline, underline-offset 2px | not applicable (no pick to build) | N/A |
| Undated "no date yet" chips doing nothing on tap | — | The caption offers Ask when on the shelf | MET |

## 10. Chat bubbles and layout

| element | spec value | build value | status |
|---|---|---|---|
| Layout contract | the picture region is fixed at its level's height; the chat fills what is left and is the only thing that scrolls; the caption slot below the pictu… | The picture resizes in place and the caption is toggled with hidden, so bubbles move on a tap | CHANGED |
| Caption minimum height | `min-height: 15px`, `margin-top: 4px`, `font-size: 13px` | The caption CSS has no min-height | CHANGED |
| Chat scroll region | `flex:1; overflow-y:auto; padding:14px 12px; display:flex; flex-direction:column; gap:10px; background:var(--bg); transition:opacity .15s` | Matches, except that there is no drag handler and no overscroll-behavior | PARTIAL |
| Bubble base | `max-width:82%; padding:9px 12px; border-radius:14px; font-size:16px; line-height:1.45` | max-width widened to 84%, plus overflow-wrap anywhere | CHANGED |
| Bubble base, earlier files | the same shape at `font-size: 14px` | not applicable (superseded) | N/A |
| Coach bubble | background `--panel`, border 1px `--line`, `align-self: flex-start`, `border-bottom-left-radius: 4px` | Coach on --panel with a --line border | MET |
| User bubble | background `--data`, colour `#fff`, `align-self: flex-end`, `border-bottom-right-radius: 4px` | User on solid --data with --onaccent text | MET |
| User bubble, hardcoded hex | `background: #0e7d78` written literally instead of `var(--data)` | Tokenised | MET |
| User bubble, translucent variant | `--bubu` = `rgba(20,108,124,.10)` light / `rgba(92,180,194,.14)` dark | not applicable (superseded) | N/A |
| Speaker label | `.who` mono `500 13px`, uppercase, letter-spacing .1em, colour `--faint`, 4px below | mono 500 13px uppercase, tracking .1em, --faint, 4px below | MET |
| System line | `.sys` centred, `500 13px/1.35 mono`, colour `--faint`, max-width 92%, single-line ellipsis | — | UNCHECKED |
| Day divider | centred, 9.5px mono, letter-spacing .12em, colour `--muted` | not applicable (no pick to build) | N/A |
| Traced bubble | `outline:2px solid var(--move); outline-offset:2px; animation: tracefade 2.2s ease-out forwards` | Removed | MISSING |
| Input bar | padding `10px 12px`, border-top 1px `--line` | Present | MET |
| Text input | height 44px, border-radius 18px, padding `0 16px`, `16px "Libre Franklin"`; a text field is 44 high with a 17px value and 16px side padding | Contenteditable composer, min-height 44 | PARTIAL |
| Send button | height 44px, min-width 44px, border-radius 22px, background `--data`, glyph "↑" | 44x44 circle with an up arrow on --data | MET |
| Send button, FD-360 | 34x34px | not applicable (superseded) | N/A |
| Composer, multi-line | a `contenteditable` div with `role="textbox"`, min-height 44px, max-height 140px; Enter sends, Shift+Enter makes a newline | Present | MET |
| Typing indicator | three 6px dots on `bounce 1s infinite` staggered .15s and .3s; a 2px cursor on `blink .7s steps(1) infinite` | Present | MET |
| Edit-summary line | `.did` one line per edit, mono 13px `--faint`, with a 6px `--move` dot bullet | Present | MET |
| First-run greeting | "I'm here whenever you want to think out loud about your family. Tell me who is on your mind." | Present | MET |
| Empty chat copy, FD-360 | "Say hello — the picture above fills in as you talk." | not applicable (superseded) | N/A |
| No modes | one agent. Coaching, app help, corrections and journaling all route from context, never from a user-visible switch | One agent, no mode switch | MET |
| Conversation drives everything | the UI is secondary; it fills gaps proactively, or the coach aims it via an inline chip | Chat is the main interface | MET |
| Demo chat timing | next bubble after 1500ms if the previous sender was the coach, 900ms if the user; sends within 1200ms of the last are ignored | not applicable (no pick to build) | N/A |

## 11. List view and event editor

| element | spec value | build value | status |
|---|---|---|---|
| The list view | full CRUD on all the user's data: a timeline list view reached by a simple button in the visual, styled like the sessions view with search, FULL SC… | Full screen, but closed by a Done link rather than a back button, with no search and no cluster dividers | CHANGED |
| Placement | the full timeline and event editor live behind a menu, off the main journey, with a one-line banner saying editing by chat also works | Behind a menu, off the main journey | MET |
| Open-list button | 44x44px, border 1px `--line`, border-radius 8px, background `--panel`; glyph three lines, viewBox `0 0 16 12`, `stroke-width="1.8"`, round caps | A hamburger in the title row labelled Timeline and settings | CHANGED |
| Back button | 44x44px, no border, colour `--data`; chevron path, viewBox `0 0 22 22`, `stroke-width="2"`, round caps and joins | A "Done" link rather than a back button | CHANGED |
| Sheet container | absolute, left/right/bottom 0, flex column, border-top 1px `--line`, top offset computed from the title row's bottom | — | UNCHECKED |
| Search bar | height 44px, `17px "Libre Franklin"`, border-radius 22px pill, border 1px `--line`; placeholder "Search events" | No search | MISSING |
| Cluster divider | sticky top, height 40px, `600 15px "Libre Franklin"`, showing the chapter label and "N moments", or "unplaced" ("No date yet" as built) | A flat, ungrouped list | MISSING |
| List row | min-height 56px, padding `8px 16px`, border-bottom 1px `--line`; line 1 `400 17px/1.3 "Libre Franklin"`; line 2 `400 13px/1.3 "IBM Plex Mono"` colo… | Rows carry a plain sentence that ellipsises | PARTIAL |
| Row summary coding | must not overflow the phone; use abbreviated codes, e.g. `S↑ A↑ F= R conflict→mom` | Plain sentences, not abbreviated codes | CHANGED |
| Row tap state | `.tl-row.on, .tl-row:active { background: var(--tint) }` | — | UNCHECKED |
| Inline editor | padding `12px 16px 16px`, background `--bg` | Present | MET |
| Editor scope | everything `schema.Event` carries, as the Pro app's EventForm does; the layout may be simplified | — | UNCHECKED |
| Event kinds | shift, birth, adopted, bonded, married, separated, divorced, moved, death | Identical to the approved set | MET |
| Relationship kinds | fusion, conflict, distance, overfunctioning, underfunctioning, projection, defined-self, toward, away, inside, outside, cutoff | Identical to the approved set | MET |
| Certainty values | unknown, approximate, certain | Identical | MET |
| Field labels | "Summary", "Details", "Where", "When", "Ended (optional)", "Certainty" | Identical | MET |
| S, A, F fields | segmented up / down / same / none | Segmented | MET |
| Δ relationship placement | at the SAME level as Δ symptom, Δ anxiety and Δ functioning: a field label under one "Shifts" heading, never its own section | — | UNCHECKED |
| Relationship field shape | not a single value: a kind AND the people involved, mover to targets. The editor must break it out into its people permutations | — | UNCHECKED |
| Relationship sub-field visibility | follows `EventForm.qml` exactly: the three shifts and Δ relationship show only for kind=shift; the targets picker appears only once a relationship… | — | UNCHECKED |
| Editor segmented chips | height 32px, min-width 44px, `500 13px "IBM Plex Mono"`, border-radius 6px; selected: border and colour `--data`, background `--tint` | — | UNCHECKED |
| Save button | full width, height 44px, background `--data`, colour `#fff`, border-radius 8px | Save filled --data at 44px | MET |
| Delete button | min-width 92px, height 44px, border 1px `--ask`, colour `--ask` | Outlined --ask, min-width 92px, shown only when editing an existing event | MET |
| Add-event button | full width, height 44px, border `1.5px solid var(--move)`, colour `--move`, border-radius 22px pill, in a footer | A plus in the title bar rather than a footer button | CHANGED |
| Menu banner copy | "You can also edit just by chatting." | Present | MET |
| Diagram / family switcher row | name `13.5px Libre Franklin`; sub `13px mono` = "N sessions · <when>"; `✓` in `--data` on the current one; current-row 3px `--data` left bar in the… | Absent | MISSING |
| Chapter Shelf | sticky name rail 92px under a 560px viewport else 132px; chapter cards `rx:12` fill `--card` stroke `--hair`, width `clamp(30, 34*sqrt(sceneCount)*… | not applicable (no pick to build) | N/A |
| Quiet Threads | sticky name rail 84px under 560px else 118px; lane gap `clamp(30, floor((H-rulerH-60)/laneCount), 54)`; three altitude modes by pixels-per-year; si… | not applicable (no pick to build) | N/A |

## 12. Type and colour tokens

| element | spec value | build value | status |
|---|---|---|---|
| Type scale, binding | screen title 17/600; body 17/400; secondary 15/400; caption 13/400-500, uppercase section headers at +0.4 tracking; absolute FLOOR 13px, mono inclu… | Nothing renders below 13px; the 17px body and title floors are not met | PARTIAL |
| Mono face | IBM Plex Mono, a utility face for data, chips, dates and labels, at 13 or 15, never below 13 | IBM Plex Mono for data and chips | MET |
| Body face | Libre Franklin, weights 400/600/800, `system-ui, sans-serif` fallback, 15px/1.5 base | IBM Plex Sans rather than Libre Franklin | CHANGED |
| Type scale as actually built | title 15px, row body 13.5px, bubbles 16px, mono utility text pinned at 13px throughout | — | UNCHECKED |
| Light palette, canonical | `--bg #f7f6f2; --ink #26312f; --faint #9aa5a1; --line #d8d5cc; --data #0e7d78; --ask #c98a1b; --move #2e9e57; --panel #fff; --shadow rgba(38,49,47,… | Amber #a8720f, green #217a44, faint #6e7a77; teal matches | CHANGED |
| Dark palette, canonical | `--bg #171d1c; --ink #e6e9e6; --faint #6d7a76; --line #31403c; --data #3fc4bc; --ask #e0a83f; --move #5fce85; --panel #1f2725; --shadow rgba(0,0,0,… | Matches throughout | MET |
| Token semantics | teal `--data` = the record; amber `--ask` = the record asking; one green `--move` = every move and action | Teal the record, amber asking, one green for moves | MET |
| Theme switching | tokens redefined under `@media (prefers-color-scheme: dark)` guarded `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`… | Tokens redefined under the media query and again under the explicit attribute | MET |
| Themeability | the design must be easily restyled so colour schemes can be A/B tested; no single scheme is assumed | Tokens only, no hardcoded hexes in components | MET |
| Palette as built, FD-362 | `--ask #a8720f` light, `--move #217a44` light, `--faint #6e7a77` light; new token `--ask-tint` `rgba(168,114,15,.1)` light and `rgba(224,168,63,.14… | As stated | MET |
| Move-language file tokens | `--data` and `--self` both `#2e9e57` light / `#5fce85` dark, i.e. the single action green; `--ask #c98a1b` / `#e0a83f` | The build splits teal and green | CHANGED |
| Two-token scheme in older files | `--data` teal for chalkboard chrome, `--move` green for the glyphs | The build uses the two-token split | CHANGED |
| Second design system | serif and mono editorial: Newsreader + Public Sans + IBM Plex Mono; `--ink #242A2E`, `--paper #F2F3F0`, `--card #FBFBF9`, `--muted #68716F`, `--hai… | Not used | MET |
| Play-by-play system | `--page #eaeeec; --card #fff; --card2 #f3f6f4; --ink #111f1c; --mute #5c6f6b; --rule #d2dbd7; --teal #0a8b80; --teal-ink #046a61; --teal-soft #d8ec… | Not used | MET |
| Verdict colours | `--ok #3a7d44` / `--bad #a4482e` light; `#6fbf7a` / `#e0785c` dark | not applicable (no pick to build) | N/A |
| SVG text default | every `<text>` inside the phone forced to `font-family:"IBM Plex Mono"; fill:var(--ink)` | — | UNCHECKED |
| Type floor enforcement | `legibility.py`: Playwright at viewport 1320x1000, device scale 2. Fails on any two visible text runs overlapping by more than 1.5px in both axes,… | Visual goldens cover the seventeen gestures; no legibility gate script found in the build | PARTIAL |
| Font size defect | the incorporated design was rejected outright on type size ("I can't read anything in the visual. everything is tiny"), and font size was confirmed… | Year labels, count pills and stage names raised off 11px | MET |

## 13. Animation and timing

| element | spec value | build value | status |
|---|---|---|---|
| Move story loop | every move animation runs the same length: 8 seconds, or an 8s multiple (10s, 12s) for the heavier storm and field marks | The moves draw and settle; nothing loops for 8 seconds | MISSING |
| No mid-animation pivot | the emotional field must not change frequency or behaviour when the cutoff lands; it stays and is obstructed | The field does not pivot because it does not animate at all | PARTIAL |
| Defined-self delay | a delay between the actor turning green and the other person settling, so cause and effect reads | Green from the first frame, no storm, so no delay to read | MISSING |
| Feel | the play-by-play must feel right: no timing gaps, no symbol gaps, no styling errors | — | UNCHECKED |
| Immediate start | a control that starts something starts it immediately, not on the next tick of a shared clock | — | UNCHECKED |
| Screen transform / filter | `.24s ease` | No screen-level transition | MISSING |
| View height change | `.25s ease` (.24s as built in chat-first-app) | The picture swaps between 158 and 252 with no ratified level model | CHANGED |
| Chapter zoom | `.6s cubic-bezier(.4,0,.2,1)` on transform plus `.6s` on opacity, opacity to 0.25, resolving at 620ms; instant under reduced motion or fast mode | No level to zoom into | MISSING |
| Chat opacity swap | `.15s` | — | UNCHECKED |
| Chapter-box pulse | opacity `.35 → 1 → .35`, `2.2s ease-in-out infinite` | No chapter box | MISSING |
| Trace fade | `tracefade 2.2s ease-out forwards`, holding solid through 40% (2400ms as built in chat-first-app) | Removed | MISSING |
| Question-mark pulse | opacity `.55 ↔ 1`, `2.8s ease-in-out infinite` | — | UNCHECKED |
| Settings pane push / pop | `.22s ease` translateX; teardown at 220ms | No settings stack | MISSING |
| Sessions sheet rise | 260ms, `cubic-bezier(.4,0,.7,.5)` opening and `cubic-bezier(.3,1.25,.5,1)` settling; wire crossfade on a family switch 300ms | No sheet | MISSING |
| Micro-symbol keyframes | `gbuzz .3s` (±2px), `gflow` stroke-dashoffset to -32 tied to its parent's duration, `gshake 1.1s` (±2-2.5px), `gsparkp .5s` (scale .75↔1.1, opacity… | Replaced by draw, drain and tremble | CHANGED |
| Move-language keyframes | `buzz .28s`; `sparkp .5s` (scale .7↔1.15); `tarrow 8s` (opacity 0 to 8%, 1 from 12-50%, 0 from 60%); `flow 1s` (dashoffset -40) or `.45s` for proje… | Replaced by draw, drain and tremble | CHANGED |
| Slide gesture | SVG `animateTransform` translate, `dur="1.2s" fill="freeze"` | — | UNCHECKED |
| Toast | opacity transition .2s, auto-dismiss at 1500ms (2200ms as built), fade-out 220ms | No toast container found | MISSING |
| Long-press threshold | 500ms for a session row; 450ms for a card title; 400ms for a crumb or a list row | Removed with the drawer | MISSING |
| Reduced motion | all transitions inside the picture forced to 0s, `.pulse` disabled entirely; in the artifact family all animation and transition durations forced t… | All animation and transition disabled inside the picture | MET |
| Finger cursor (gallery only) | 22x22px circle, `margin:-11px 0 0 -11px`, background `--finger`, border `2px var(--fingerring)`; move `left .22s ease, top .22s ease`, opacity `.15… | not applicable (no pick to build) | N/A |
| Shared 12s demo loop | one fixed cycle, same beats on every phone: 0-1 idle, 1-3 open, 3-5 pick, 5-7 re-enter, 7-10 edit, 10-12 close and save | not applicable (no pick to build) | N/A |
| Loop control defect | clicking "loop" on a gallery example does not start the animation | — | UNCHECKED |
| Keyframes as built, FD-362 | `draw .6s ease-out forwards` dashoffset 240 to 0; `drain 1.4s linear infinite` dashoffset -24; `tremble 1.2s linear infinite` five-step ±2px holdin… | Present | MET |

## 14. Tap and scroll behaviour

| element | spec value | build value | status |
|---|---|---|---|
| Tap target floor | 44x44px minimum on every interactive element, 48 preferred for primary actions; the visual may be smaller (a 24px glyph inside a 44x44 button); 8px… | Chips, picture marks and caption buttons all raised to 44 | MET |
| Spacing | side gutters 16px; related items 8px; groups 16-24px; section breaks 32px; content never closer than 16px to the phone edge | — | UNCHECKED |
| Scrolling | every scroll area supports wheel, trackpad, touch drag AND mouse drag; a drag handler is required; `touch-action: pan-y`; `overscroll-behavior: con… | The chat and the menu scroller are plain overflow-y auto: no drag handler, no overscroll-behavior, no touch-action | MISSING |
| Momentum | wheel scrolling in addition to click-and-drag, with momentum, so the surface feels native on iOS and macOS | No drag handler | MISSING |
| Outer-page scroll defect | a demo's scroll target applied to the outer page made the gallery scroll itself after a while | — | UNCHECKED |
| The coach keeps the chalk | every tap loops into chat; the coach never hands over the chalk. A drawing is conjured by the coach, never by the user driving the picture | Only a coach turn or the Play action draws | MET |
| Look then say | the first tap looks and is free, showing a title or a caption; the second tap is a chip and speaks | Taps look, chips speak | MET |
| Every tap is learning data | including looks that send nothing; visible to the coach as context, and first on the A/B test list | — | UNCHECKED |
| Picture simplicity | the picture stays exceedingly simple; one tap to reveal a title is acceptable; crowding means doing too much | One wire, one caption row | MET |
| Label band tap | one 44px band spanning all three label rows at top 45px, width x1-x0. The row nearest the tap wins, by `abs(ROWS[row] + 7.5 - y)` | Ported as rowAt: nearest row by vertical distance | MET |
| Moment tap zones | buttons of width `(x1-x0)/nz` where `nz = max(1, floor((x1-x0)/44))`, so zones are always at least 44px wide, at top 89px, height 44px | 44px zones, repeated taps cycle through the events in the zone | MET |
| Hit press and focus states | `:active { background: var(--tint) }`; `:focus-visible { outline: 2px solid var(--data); outline-offset: -2px }` | Focus ring present at -2px on picture hit zones | MET |
| Second tap on a selected moment | jumps to the source: scrolls the chat to the bubble where the moment was coded and highlights it with `.traced` for 2.2s | No jump to the coded message | MISSING |
| A new coach turn | clears the current selection and re-lights the newly named set | The coach's message lights the moments its chips name | MET |
| Tap a datum to see where it was mentioned | as demonstrated in the `base` frame | Not built | MISSING |
| Episode hover | `filter: brightness(1.2)` | not applicable (no pick to build) | N/A |
| Caption actions as built | "[Ask about this]", "[Ask when]" on the shelf, plus a "Play" button when the selection maps to a stretch | Present | MET |
| Tap a chat bubble | traces to the picture mark it refers to, with a 2.2s highlight fade | Not built | MISSING |
| Tap an amber question mark | opens the question inline, or aims the picture at the relevant lane | not applicable (no pick to build) | N/A |
| Oversized hit areas | glyphs wrapped in a transparent hit shape drawn well beyond the visible mark | not applicable (no pick to build) | N/A |

## 15. Other

| element | spec value | build value | status |
|---|---|---|---|
| Push notifications | default to few, then experiment upward; proactive messaging defaults to near zero, firing only when a dated fact lines up with a real anniversary | No proactive messaging built | MET |
| "While it's calm" prompting | valuable, an A/B test candidate | — | UNCHECKED |
| Design-round method | mockups with one-line captions, wide divergence first, converge later; land ONE concept per area; no polish before a pick; idea rounds on cheaper m… | not applicable (no pick to build) | N/A |
| How options are described | common words, explicit and specific; no coined vocabulary, no clever framing, no egocentric captions | not applicable (no pick to build) | N/A |
| Symbols in context | symbols must be shown inside the real design, not as standalone concepts; pixel-perfect interactive mockups come before code | not applicable (no pick to build) | N/A |
| Visuals not tables | design decisions must be communicated as visuals, never as tables | not applicable (no pick to build) | N/A |
| Platform | the rebuild is web-first: simple, light, elegant, easy dev flow, easy release and distribution, no Qt tie | Web-first, no Qt tie | MET |
| Manual editing alongside chat | stays, with full bidirectional reactivity; chat tool calls control everything in the app | The timeline list and editor exist alongside chat | MET |
| Friction reports | the app self-files them; chat can explain app usage from the reference manual | — | UNCHECKED |
| Clusters | model-derived and stored; the model may group and name, never invent members | Model-derived and stored | MET |
| Underlying data model | a `Change` model of per-command deltas grouped by turn id, undo by compare-and-set; an `Interaction` model recording every look, say, chip tap and… | — | UNCHECKED |
| The six journeys that check the build | first conversation from an emailed link; correction via chat; cluster tap to chip to play-by-play; the coach draws a triangle via a chip; resume a… | — | UNCHECKED |
| Beta deferrals | proactive messages; a "what you said" provenance view; lane pinning; Pro migration; notability import; sharing; formal undo beyond per-turn; era co… | — | UNCHECKED |
| Post-mortem warning | the Learn tab failed because the data gave no clear trends, and inferring never worked | — | UNCHECKED |
| Fixture records, session-menu round | four, all must keep working: a sparse personal record (~12 moments, 9 sessions, one hand-renamed); a dense clinical record (~28 sessions, 31 moment… | — | UNCHECKED |
| Fixture records, account round | four: a personal account with 1 diagram and 2 licences; a professional with 30 diagrams and multi-seat licences; an empty account that must read se… | — | UNCHECKED |
| Crowding measurements | 210 chapters hold 2 or more moments; the median chapter holds 4; 17% cannot fit labels even at 6 stacked lanes; 90th-percentile overflow 2.1x, wors… | — | UNCHECKED |
| Verification harness rules | fails on any console or page error, any element overflowing its phone by more than 2px (transform and clip exempt), horizontal page scroll, a title… | — | UNCHECKED |
| Never real data | all fixture names and emails are synthetic placeholders. One real full name is embedded in a bonds list in the session-menu scaffold fixture and mu… | — | UNCHECKED |
| Out of scope | `/Users/patrick/demos/mockups/` (`aha-sources.html`, `timeline-headlines.html`) are dated April 2026, outside the window, and use a different dark… | not applicable (no pick to build) | N/A |
| Pro app, right toolbar order | menu items, buttons and tabs must all follow the keyboard-shortcut order: timeline, triangles, chat, settings | not applicable (no pick to build) | N/A |
| Pro app, main menu and splitter | the main menu must use the standard macOS menu bar; the right-drawer splitter must draw in the dark-mode colour, not white | not applicable (no pick to build) | N/A |
| Pro app, case properties tabs | the same order as the toolbar buttons, using the same tab widgets | not applicable (no pick to build) | N/A |
