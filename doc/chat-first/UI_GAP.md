# UI_GAP — UI_SPEC against the current build

Every row of `UI_SPEC.md` set against branch FD-362. Each build value was read from the source in this worktree and cites the file and line it came from: `web/index.html`, `web/src/theme.css`, and `web/src/*.ts`. Earlier audit write-ups were used only as pointers to where to look, never as the finding — several of their status claims did not survive reading the code. A row says UNCHECKED when the behaviour is not decidable from the front-end source, such as a backend rule or a copy string served by the API.

Where UI_SPEC carried a conflict, the verdict here is against the resolved value, not against the losing source. Seven rows moved when the 36 conflicts were resolved: the coach-requested span band, the people appearing only when a move needs them, the amber question mark and the per-move advance all became MET, and the web frame width moved to NEEDS-OWNER, because resolution 31 set that number as a team default rather than by a ruling.

Statuses: **MET** the build matches the spec value · **PARTIAL** part of it is there · **CHANGED** the build does something different · **MISSING** absent · **UNCHECKED** no evidence either way · **NEEDS-OWNER** the build is defensibly different rather than wrong, because the value it differs from is a team default or an unruled call — do not act on this row without asking · **N/A** the row is a superseded option, an unpicked option, or a source a resolution ruled against, so there is nothing for the build to match.

| status | rows |
|---|---|
| MET | 131 |
| PARTIAL | 45 |
| CHANGED | 69 |
| MISSING | 110 |
| NEEDS-OWNER | 3 |
| UNCHECKED | 23 |
| N/A | 62 |
| **total** | **443** |

| group | MET | PARTIAL | CHANGED | MISSING | NEEDS-OWNER | UNCHECKED | N/A |
|---|---|---|---|---|---|---|---|
| 1. App shell and navigation | 4 | 4 | 6 | 6 | 1 | 0 | 4 |
| 2. Sessions / discussions drawer | 0 | 0 | 0 | 25 | 0 | 3 | 11 |
| 3. Settings and account | 1 | 1 | 0 | 24 | 0 | 1 | 10 |
| 4. Picture at rest — the sentence spotlight | 32 | 3 | 10 | 6 | 0 | 0 | 6 |
| 5. Picture symbols — one row per symbol | 10 | 11 | 27 | 11 | 0 | 1 | 3 |
| 6. Chalkboard / moves board | 4 | 2 | 5 | 12 | 0 | 1 | 4 |
| 7. Show-tool view kinds | 0 | 5 | 0 | 0 | 1 | 1 | 0 |
| 8. Play-by-play | 7 | 7 | 6 | 4 | 0 | 3 | 0 |
| 9. Chips | 9 | 4 | 3 | 2 | 0 | 1 | 2 |
| 10. Chat bubbles and layout | 13 | 1 | 3 | 2 | 0 | 0 | 6 |
| 11. List view and event editor | 25 | 0 | 0 | 1 | 1 | 0 | 2 |
| 12. Type and colour tokens | 9 | 3 | 5 | 0 | 0 | 0 | 1 |
| 13. Animation and timing | 2 | 2 | 3 | 13 | 0 | 1 | 3 |
| 14. Tap and scroll behaviour | 11 | 2 | 1 | 4 | 0 | 0 | 2 |
| 15. Other | 4 | 0 | 0 | 0 | 0 | 11 | 8 |

## 1. App shell and navigation

| element | spec value | build value | status |
|---|---|---|---|
| Phone frame | 400x820px, max-width 100%, background `--panel`, border 1px `--line`, border-radius 26px, box-shadow `0 8px 40px var(--shadow)`, overflow hidden, `… | No phone frame; `.app` is `max-width:460px`, `height:100dvh`, with left and right hairlines above 461px (theme.css:63-74) | CHANGED |
| Phone frame, alternate | 390px wide, border-radius 36px, padding 10px, box-shadow `0 18px 40px -22px rgba(20,30,34,.35)` | not applicable (no pick to build) | N/A |
| Screen layer | absolute inset 0, `transition: transform .24s ease, filter .24s ease` | `.screen{flex:1;min-height:0;display:flex;flex-direction:column}` with no transform or filter transition (theme.css:75) | CHANGED |
| Status bar | padding `10px 22px 2px`, font `600 13px -apple-system, system-ui`; time "9:41"; icons gap 5px, signal 16x10px clip-path bars, wifi 14x10px half-pil… | Browser chrome; the title row pads by `env(safe-area-inset-top)` (theme.css:83) | N/A |
| App header ("Family Diagram" bar) | — | No app header (index.html:15-20) | MET |
| Title row | height 44px, padding `0 14px`, border-bottom 1px `--line`, flex, gap 10px, directly under the status bar and above the picture | `.titlerow` height 44px, padding `env(safe-area-inset-top) 10px 0`, border-bottom 1px `--line`, gap 8px (theme.css:77-85). Holds the title and one icon button, no avatar (index.html:15-20) | PARTIAL |
| Title text | `600 15px/1.2 "Libre Franklin"`, colour `--ink`, flex 1, ellipsis overflow | `.ttl{flex:1;font:600 17px/1.2 var(--sans)}` (theme.css:86). Size meets the 17/600 floor; the text is the literal string "Your family" (index.html:16) | PARTIAL |
| Title text size | 15px in every built mockup against the binding 17/600 screen-title floor | `600 17px` (theme.css:86), which meets the binding floor rather than the mockups' 15px | MET |
| Title default text | the current diagram/family name, e.g. "your family" or a professional's client diagram name | Hardcoded "Your family" in the markup; no code path writes `.ttl` (index.html:16, grep over web/src) | CHANGED |
| Account avatar | 44x44px circle, border-radius 50%, background `--panel`, border `1.5px solid var(--data)`, colour `--data`, initial in `500 13px "IBM Plex Mono"`,… | No avatar. The upper right is `.iconbtn#menu-open`, 44x44, an 18x14 three-line SVG at stroke-width 1.7, `aria-label="Timeline and settings"` (index.html:17-19; theme.css:87-98) | CHANGED |
| Avatar size | UI_STANDARDS.md and API2.md prose say a 30px (standards text says 40px) visual inside a 44x44 target; the built CSS fills the whole 44 | No avatar element exists | MISSING |
| Avatar correction | the account avatar was too small and must meet the shared size standard | No avatar element exists | MISSING |
| Nav button (back / close) | 44x44px, font `600 18px system-ui`, colour `--data`, no border or background, inline-flex centred | No picture-level nav buttons; the picture has no levels (picture.ts render) | MISSING |
| Back chevron, settings stack | `‹`, min 44x44px, colour `--data`, font `500 19px mono`, inserted at the start of the title row | No settings stack; the menu screen closes with a `.btn.link` reading "Done" (index.html:44) | MISSING |
| Picture-region corner slots | `.corner` absolute top 2px; `.l{left:4px}`, `.r{right:4px}`; each holds a nav slot and a concept slot | No corner slots; `.pic` holds a pin label, the view and the caption (index.html:23-30) | MISSING |
| Crumb line | `500 13px "IBM Plex Mono"`, colour `--faint`, min-height 15px, centred; sentence-spotlight sets `margin: 0 48px` to clear the corner buttons | No crumb. `.pin-label` carries "Family time line" at the left and the picture's state at the right, `400 13px mono`, uppercase, tracking .08em (index.html:24-27; theme.css:102-119) | CHANGED |
| Crumb line, coach-screen variant | `500 10.5px mono`, min-height 15px, padding `0 4px`, link colour `--data` no underline | not applicable (no pick to build) | N/A |
| Bottom tab bar | 50px height, absolute bottom 0, border-top 1px `--line`, 2 tabs x 200px, icon 20x20 + 10px label, active `--data`, inactive `--faint` | Absent | N/A |
| Signed-out screen | full-phone overlay z-index 25, centred column gap 16px; app name `800 21px "Libre Franklin"`; who line `500 13px mono`; sign-in pill border 1px `--… | No signed-out screen and no sign-out control anywhere in web/src | MISSING |
| Focus ring, global | `outline: 2px solid var(--data)`, offset 1px, and -2px inside picture hit zones | `:focus-visible{outline:2px solid var(--data);outline-offset:1px}` (theme.css:61) and `-2px` on picture hit zones (theme.css:175) | MET |
| Pressed state, global | every interactive element has a visible pressed state | `.ss-hit:active{background:var(--tint)}` (theme.css:174) and `.row.on`/`.chip.ask:active` (theme.css:460,380). No pressed state on `.iconbtn`, `.btn` or `.send` | PARTIAL |
| Button and icon consistency | every button and icon meets one shared size and usability standard | `.iconbtn` and `.send` are 44x44 (theme.css:87-98,406-416), but `.btn` is `min-height:36px` (theme.css:429-441), so the Play and Done controls sit under the floor | PARTIAL |
| App frame width, web | at phone width, `max-width: 400px` centred, so every mockup value transfers without rescaling; above that, the desktop drawings where they exist (t… | `.app{max-width:460px;margin:0 auto}` with hairlines above 461px (theme.css:63-74). One fixed width, matching neither the 400px phone width nor any desktop treatment. Resolution 31 set those numbers as a team default with the owner unasked, so this is a difference from a team preference, not from a ruling | NEEDS-OWNER |
| PWA shell | manifest, service worker at `/companion/sw.js`, `icon.svg`, Google Fonts preconnect | manifest link, icon, Google Fonts preconnect (index.html:6-11) | MET |
| Menu button label | a control's label must name what it does | `aria-label="Timeline and settings"` (index.html:17); the menu screen's own title is "Timeline" and it holds a list and an editor, no settings (index.html:40; menu.ts:36-55) | CHANGED |

## 2. Sessions / discussions drawer

| element | spec value | build value | status |
|---|---|---|---|
| Session door — the pick | the button plus a swipeable, searchable sessions overlay, as built in the `family-sections` option | No sessions surface. web/src holds no session list, sheet, scrim or drawer | MISSING |
| Door placement | beside the chat input, not in the title row | `.inbar` holds the composer and the send button only (index.html:32-36) | MISSING |
| Sessions button, final look | 34px circle, hairline 1px `--line` border, `--bg` fill, three-line icon 16x12 (`M1 1h14M1 6h14M1 11h14`) stroke 1.6 round caps at 80% opacity, insi… | No sessions button in the markup or in web/src | MISSING |
| Sessions glyph, as built in the avatar round | `.sessglyph` 44x44px, no border or background, font-size 22px | not applicable (superseded) | N/A |
| Sessions bottom sheet | height 92% of the frame (top edge y=66), background `--panel`, border-radius `18px 18px 0 0`, box-shadow `0 -8px 30px var(--shadow)`, `transform: t… | No sheet, no scrim | MISSING |
| Sheet grabber | 36x5px, border-radius 3px, `--line`, in a 22px handle strip | Absent | MISSING |
| Sheet open / close gestures | drag up from the input bar 40px or more opens; tap the scrim closes | Absent | MISSING |
| Sheet search field | 36px high, border-radius 18px pill, 13.5px, border 1px `--line`, focus border `--data`, placeholder "Search sessions and families" | No search input anywhere in web/src | MISSING |
| Search field size | 36px high and 13.5px text against the binding 44px control height and 17px text-field value | Absent | MISSING |
| Family section header | 40px sticky, family name `600 13px`, 60x14px wire thumbnail, "last: <summary>" `10.5px mono`, a 28x28px green "+" at the right | Absent | MISSING |
| Family section rows | 54px, sorted by recency, no Today/Yesterday subgroups inside a family, each family collapsed to its 3 most recent plus a 36px "N more…" row | Absent | MISSING |
| Session row, default | height 56px, padding `0 14px 0 16px`, border-bottom 1px `--line`, background `--panel` | Absent | MISSING |
| Session row, title-and-date only | height 44px, no summary line | not applicable (no pick to build) | N/A |
| Session row, with wire thumbnail | height 60px, adds a 48x12px wire thumbnail at the left and a 10px mono picture-state word under the date | not applicable (no pick to build) | N/A |
| Row title | `15px/1.3`, nowrap ellipsis, ~30 chars; untitled shown in `--faint` | Absent | MISSING |
| Row summary | `12.5px/1.3`, `--faint`, nowrap ellipsis | Absent | MISSING |
| Row side / date | `500 10.5px/1.3 mono`, `--faint`, tabular-nums, max-width 44% | Absent | MISSING |
| Row side text size | 10.5px against the binding 13px absolute floor | Absent | MISSING |
| Current-session marker | `::before` 3px left bar in `--data`, full row height | Absent | MISSING |
| Row press feedback | background `--tint` | Absent for sessions; the timeline list has `.row.on{background:var(--tint)}` (theme.css:460) | MISSING |
| Renamed-row marker | `✎` glyph, 9px, `--faint`, 4px left margin | Absent | MISSING |
| Sticky group header | position sticky top 0, height 20px, line-height 20px, padding `0 16px`, `500 10.5px mono`, uppercase, letter-spacing .04em, `--faint`, background `… | Absent | MISSING |
| Rename, inline field | `15px/1.3 Libre Franklin`, colour `--ink`, background `--bg`, border 1px `--data`, border-radius 4px, padding `1px 6px`, text pre-selected | No rename path in web/src | MISSING |
| Rename revert target | revert to the coach's auto title, or to the previous title | Absent | MISSING |
| New-session button | pinned in the sheet footer, full width, 40px high, border `1.5px solid var(--move)`, border-radius 20px, green label "New session with <family>" | Absent | MISSING |
| Empty states, verbatim | "Past conversations collect here" when there are none; "No sessions match" when a search finds none. Mono 11px, `--faint`, centred, 18px padding | Absent. The only empty copy is "Nothing on your timeline yet." (menu.ts:40) | MISSING |
| Sort order | newest activity first; never reorders while the view is open | — | UNCHECKED |
| Another user's session | returns 404, not 403 | — | UNCHECKED |
| `Discussion.title` | nullable column, auto-titled by the coach after the first exchange, hand-editable | — | UNCHECKED |
| Two-way traceability, picture to session | a selected moment shows a chip reading `coded in: <session title> · <short date> →`, title truncated at 30 chars | The caption row offers only an ask chip and a Play button (main.ts:184-197). No coded-in chip, no session jump, no traced outline anywhere in web/src | MISSING |
| Toast | `500 13px mono` (11px in scaffold), background `--ink`, colour `--panel`, border-radius 14px, padding `6px 12px`, opacity 0 to .92 over .2s, auto-d… | No toast in index.html or theme.css | MISSING |
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
| The app-level view | `settings-nested`: an iOS-Settings list where every row pushes its own full page with a back chevron | No settings screen. index.html has two screens, chat and menu (index.html:22,39) | MISSING |
| Entry point | the account avatar in the title row; no default click handler on the avatar, each surface wires its own | No avatar to tap | MISSING |
| Pane stack container | `.sn-stack` absolute, bottom 0, overflow hidden, top offset measured at runtime from the bottom of the title row | Absent | MISSING |
| Pane push / pop | `transform: translateX(100%)` to none, `.22s ease`; the pane beneath parallaxes to `translateX(-28%)`; teardown after 220ms | Absent | MISSING |
| Group / section | margin `14px 0 0`, background `--panel`, 1px `--line` top and bottom; header `500 13px mono`, uppercase, letter-spacing .06em, padding `0 16px 5px` | Absent from settings; the editor has `.sec` at `600 15px` (theme.css:474) | MISSING |
| Section header tracking | .06em here, .04em elsewhere, against the standard's flat +0.4 tracking | Absent | MISSING |
| Row (push type) | min-height 44px, padding `7px 16px`, border-top 1px `--line`; label max-width 52%, `13.5px Libre Franklin`; value right-aligned `13px mono` in `--f… | Absent | MISSING |
| Row label size | 13.5px against the binding 17/400 body floor | Absent | MISSING |
| Profile cell (root, top) | min-height 44px, padding `13px 16px`; face 48x48px circle, border `1.5px solid var(--data)`, `19px mono` initial or silhouette SVG; name `600 15px… | Absent | MISSING |
| Root list order | profile cell; group of Coach ("speak on" / "speak off") and Appearance (theme); group of Your diagrams (count) and Plan and licenses ("<n> licence(… | Absent | MISSING |
| Preferences content | first name, last name, birthdate; a way to sign out | No UI reads or writes first name, last name or birthdate; no such field in web/src | MISSING |
| Preferences object fields | `speak`, `proactive`, `mode`, `theme`, `first_name`, `last_name`, `birthdate` | — | UNCHECKED |
| Account content | your diagrams (including the many-diagram professional case), licenses, beta plan and pricing, email and login method | No account UI in web/src | MISSING |
| Profile page fields | First name, Last name, Birthdate (`type=date`), with the note "Your birthdate anchors your own line on the picture."; input row right-aligned `13.5… | Absent | MISSING |
| Speak-replies control, settings | a real iOS switch 51x31 inside a row of 44 or more, or a 24x24 checkbox with a 17px label in a 44 row. Never a native unsized checkbox | Absent | MISSING |
| Speak-replies checkbox as built | native checkbox 15x15px, `accent-color: var(--data)` | Absent | MISSING |
| Speak-replies row, chat view | min-height 44px, padding `6px 16px`, border-top 1px `--line`, label `500 17px mono` "speak replies", checkbox 24x24px `accent-color: var(--data)`;… | No checkbox between the chat and the input bar (index.html:31-37) | MISSING |
| Coach page | "Speak replies" switch; "Voice or text" segmented text/voice; "How often" segmented never/rarely/weekly; note "The coach never messages first unles… | Absent | MISSING |
| Segmented control | 32px high inside a 44 row, each segment 44px wide or more; `13px mono`, padding `4px 8px`, border 1px `--line`, adjoining segments `margin-left: -1… | `.seg{height:32px;min-width:44px;padding:0 12px;font:500 13px var(--mono);border-radius:6px}`, `.seg.on` border and colour `--data` on `--tint` (theme.css:498-509). Matches the ruling, but exists only inside the event editor | PARTIAL |
| Appearance page | theme segmented: system, light, dark | Absent; theme follows `prefers-color-scheme` with a `[data-theme]` override and no control to set it (theme.css:20-47) | MISSING |
| Diagrams page row | name `13.5px Libre Franklin`; sub `13px mono` = "N sessions · <when>"; `✓` tick in `--data` on the current diagram; row shows " · in use" when free | Absent | MISSING |
| Diagrams search threshold | search box appears at 6 or more diagrams (built), "more than about eight" (option prose), more than 8 (chat-first-app build) | Absent | MISSING |
| Plan and licenses page | badge `13px mono` border 1px `--data` radius 10px padding `3px 9px`; price `600 16px Libre Franklin`; manage button border 1px `--data` radius 14px… | Absent | MISSING |
| Sign-in page | Email row, Method row, "Sign out" posting to `/training/auth/logout` | Absent | MISSING |
| Sign out row | full width, centred, `13px mono`, colour `--ask`, min-height 44px, its own last group; no confirm dialog built | Absent | MISSING |
| No duplicate content | no surface repeats another surface's list; one home per setting. A second appearance is a named shortcut writing the same value | Nothing is duplicated because only one surface exists | MET |
| Switch as built (chat-first-app) | 51x31px, thumb 27x27px white circle, left 2px to 22px, `transition: left .15s ease` | No switch control in web/src | MISSING |
| `avatar-popover` | floating popover `top:76px; right:10px; width:300px; max-height:470px`, radius 14px, shadow `0 10px 34px`, origin top right, `scale(.86)` to none `… | not applicable (superseded) | N/A |
| `account-page` | full-screen push from the right, `.24s ease`; profile face 46x46px; fixed 104px label column; full-width red sign-out | not applicable (superseded) | N/A |
| `right-drawer` | drawer ~85% width from the right; switch 38x22px; sheet radius `14px 14px 0 0`, `.2s ease` | not applicable (superseded) | N/A |
| `bottom-sheet-tabs` | sheet to 70% height, full state `calc(100% - 46px)`, radius `16px 16px 0 0`, `.24s ease` transform and `.2s ease` height; 22px grab handle | not applicable (superseded) | N/A |
| `picture-flip` | the picture area flips, `rotateY(90deg)` to none `.22s ease`, backface hidden; control pills `13px mono` radius 9px; 66px key column | not applicable (superseded) | N/A |
| `profile-card-first` | full page, opacity 0 to 1 `.2s ease`; card avatar 52x52px; name `800 21px Libre Franklin` 2-line clamp; 28x28px pencil button | not applicable (superseded) | N/A |
| `diagrams-first` | page slides up `.24s ease`; footer sheets max-height 74%, radius `14px 14px 0 0`; rows 56px with a 3px `--data` current bar | not applicable (superseded) | N/A |
| `you-conversation` | the chat thread swaps to a conversation about the user; inline switch 34x20px; diagram card list max-height 154px | not applicable (superseded) | N/A |
| `two-level-popover` | level 1 small popover, level 2 full push at `top:72px` `.22s ease`; face 30x30px; switch 38x21px | not applicable (superseded) | N/A |
| `two-level-popover` diagram button | `.tl-dg` full-width row, `height:42px`, padding `0 12px`, border-bottom 1px `--line`; name `500 13px "Libre Franklin"` ellipsis; sub `500 13px mono… | not applicable (superseded) | N/A |

## 4. Picture at rest — the sentence spotlight

| element | spec value | build value | status |
|---|---|---|---|
| The picture's place | above the chat, permanently on screen, editable | `.pic{flex:none}` above `.chat{flex:1}` inside the chat screen, always rendered (index.html:23-31; theme.css:101,256) | MET |
| The picture's nature | an utterance, never a workspace. No legends, no filter UI, no selection furniture. The system decides what matters and shows it | No legend, filter or selection furniture in the picture markup (picture.ts render) | MET |
| Detail level | cartoon-level, strip-small, one or two lanes; surface one or two correlations, never a dataset | One wire, one dot per moment, at most three word rows (picture.ts:305-380) | MET |
| Chosen chapter view | sentence spotlight: the coach's message lights the events it names, the rest stay dim dots, up to three rows of words tied to their dots by leader… | `spotlight()` sets the named events and everything else drops to `baseOpacity` (picture.ts:112-119; spotlight.ts:72-74) | MET |
| Level heights | resting wire 78px, chapter 158px, moves board 264px. A different height is allowed only if the proposal states what chat area it gives up | Two heights only: `PIC_H` 158 and `STAGE_H` 252, swapped by `staged` (picture.ts:41,283-285). No 78 resting level and no 264 board | CHANGED |
| Picture container | `.pic` position relative, border-bottom 1px `--line`, padding `4px 10px 8px`, background `--panel` | `.pic{flex:none;padding:6px 0 4px;border-bottom:1px solid var(--line)}` (theme.css:101) | PARTIAL |
| View height transition | `transition: height .25s ease` (.24s as built in chat-first-app) | No height transition on `.view` or `.ss`; the height is set inline per render (theme.css:120-122; picture.ts:377) | MISSING |
| Picture height stability | the picture is pinned at its level's height by both its wrapper (`height:158px; flex:none`) and its viewBox, so nothing below it moves | `.ss` height is written inline as `staged ? 252 : 158` on every render (picture.ts:285,377), so a move going on stage resizes the picture in place and moves everything below it | CHANGED |
| Caption slot | `font-size:13px; margin-top:4px; min-height:15px`, colour `--faint`, padding `0 4px` | `.caption` has no `min-height` (theme.css:247-252) and is toggled with the `hidden` attribute (index.html:29; main.ts:173-185), so it leaves and re-enters the layout | CHANGED |
| Caption strip, scaffold variant | 11.5px `--faint`, min-height 15px | not applicable (superseded) | N/A |
| Resting wire height | 78px, viewBox `0 0 380 78`, x0=16, x1=364 | No 78px level exists; the wire sits at y=99 inside the 158px picture (spotlight.ts:10-12) | CHANGED |
| Baseline | `<line x1=16 y1=46 x2=364 y2=46 stroke="var(--line)" stroke-width="1.5">` | `<line class="wire">` at the wire y, `stroke:var(--line);stroke-width:1.5` (picture.ts:325; theme.css:125) | MET |
| Chapter box | `<rect y=12 height=52 rx=8 fill="var(--data)" opacity="0.07">` plus an outline rect `fill=none stroke="var(--data)" stroke-width=1 opacity=0.35` ca… | No cluster rect. A bracket path `.brk` is drawn over the focused stretch, `stroke:var(--data);stroke-width:1.2`, and only when no words are on the picture (picture.ts:463-475; theme.css:139) | CHANGED |
| Chapter box pulse | opacity `.35 → 1 → .35`, `2.2s ease-in-out infinite`; disabled under reduced motion | No pulse keyframe in theme.css | MISSING |
| Sparse chapter dots | one `<circle r="4.5" fill="var(--data)">` per moment, evenly spaced across the box | `.dot{fill:var(--data)}` at `dotRadius` (picture.ts:399; theme.css:135) | MET |
| Dense chapter glyph | more than 8 moments collapse to `<circle r="11" stroke="var(--data)" stroke-width="1.6">` with a count text at font-size 10 | No count glyph. Density is handled by shrinking the dot instead (spotlight.ts:66-68) | CHANGED |
| Count text size | 9-10.5px against the binding 13px floor | No count text | MISSING |
| Chapter year-range label | `<text y=26 font-size="10.5" fill="var(--faint)">` two-digit years | No resting wire level exists, so the 10.5px two-digit range this row describes is never drawn. The chapter picture's own year labels are the separate ratified 13px `.ss-yr` row, which is MET (picture.ts:361-366; theme.css:127-132) | MISSING |
| Gap question mark | `<text font-size="13" fill="var(--ask)">?</text>`, shown only when the gap between chapters is 4 years or more | `.qm.small` at 13px, `fill:var(--ask)`, drawn per unresolved question and suppressed within 16px of another, not on a 4-year gap rule (picture.ts:489-501; theme.css:178-179) | CHANGED |
| Hint text | `<text x=16 y=74 font-size="9" fill="var(--faint)">tap a chapter</text>` | No hint text on the picture | MISSING |
| Empty-record copy | "Nothing on your line yet — it draws itself as you talk.", `font-size:13px; color:var(--faint); padding:10px 6px` | No prose empty state. The empty picture is a dashed wire plus a centred "?" (picture.ts:296-306) | CHANGED |
| Empty wire, as built FD-362 | dashed line `stroke-dasharray: 3 6` plus a centred "?" | `.wire.empty{stroke-dasharray:3 6}` plus a centred `.qm` (picture.ts:299-301; theme.css:126) | MET |
| At-strip-scale vocabulary | exactly three marks: a line, dots, and the amber question mark. Bands, ranges, fades and ticks belong to the expanded view only | Line, dots and the amber question mark, with a `.span` band only when the coach asks for a span view (picture.ts:477-484; theme.css:140), which resolution 14 allows | MET |
| Every mark speaks | a plain sentence on tap, e.g. "sleep got worse, around 1996, give or take a year". No legends anywhere | A selected moment writes meta plus two wrapped rows onto the picture (picture.ts:411-426) | MET |
| No progress bar | no data-completeness bar, no notion of being finished; the readout shows what more data buys, as specific answerable questions | No progress element in web/src | MET |
| Questionnaire register | rejected; conversation drives everything and the picture is only a secondary way to fill gaps | No form or questionnaire in web/src | MET |
| Lane filter buttons | rejected; hiding lanes by hand is "a data project no one wants" | No filter control in web/src | MET |
| Click-to-filter or select people | rejected, same reason | The only picture taps are the label band, the moment zones and the shelf (picture.ts:369-380) | MET |
| Lanes | conversation-aimed pairs chosen by the coach or by user pins, never an always-on grid, never a filter UI | One wire, no lanes (picture.ts render) | MET |
| The lane-design round | the whole round rejected as clunky and uncommunicative | not applicable (superseded) | N/A |
| Clusters | central and kept; the valuable thing to show, an innovation for Bowen theory from this app's timeline data | Chapters arrive with the timeline and are read, never invented, by the page (types.ts `Chapter`; picture.ts:229-231) | MET |
| Bands | good but data-gated: each captured span earns a band; dated relationship spans barely exist outside the hand-curated case, so they are a coach elic… | `.span` is drawn only for a coach span view, `fill-opacity:0.14` (picture.ts:477-484; theme.css:140). No data-gated relationship bands | PARTIAL |
| The FD-360 expanded picture | rejected: boxes scattered in lanes too sparse to read as a common timeline, question-mark tags irregularly placed | not applicable (superseded) | N/A |
| Green boxes, blue-dot-and-bar boxes, white vertical and dashed lines | rejected as unreadable without labels, with no room for labels | not applicable (superseded) | N/A |
| Horizontal timeline scrolling | required, with pan and zoom that handle irregular spans without dead space | No pan or zoom. `rescale()` fits the shown moments to the width, and the coach's aim changes the range (picture.ts:233-245) | CHANGED |
| Chapter view geometry (level 2) | height 158, viewBox `0 0 W 158`, x0=16, x1=W-16 (W = phone client width, default 378); wire at y=99; year labels at top 136; label rows at y 44 / 5… | `CH 7.8`, `ROWS [44,59,74]`, `WIRE 99`, `YEAR_TOP 136`, `PIC_H 158`, `X_PAD 16`, `ZONE 44` (spotlight.ts:8-15) | MET |
| Chapter wire line | `<line y1=99 y2=99 stroke="var(--line)" stroke-width="1.5">` | `stroke:var(--line);stroke-width:1.5` at y=99 (theme.css:125; picture.ts:325) | MET |
| Dot density rule | base radius by count: 12 or fewer = 4.5; 30 or fewer = 3.5; 60 or fewer = 2.6; above that = 1.8 | `n<=12?4.5:n<=30?3.5:n<=60?2.6:1.8` (spotlight.ts:66-68) | MET |
| Base dot opacity | 0.35 once anything is lit; otherwise 1 when the chapter holds 24 or fewer moments, 0.6 above that | `named ? 0.35 : n<=24 ? 1 : 0.6` (spotlight.ts:72-74) | MET |
| Plain dot | `<circle cy=99 r=r0 fill="var(--data)" opacity=baseOp>` | `<circle class="dot" r=radius opacity=baseOp>` (picture.ts:399) | MET |
| Lit ordinary moment | `<circle r="5" fill="var(--data)">` at its stacked y | `r=5` at full opacity when lit (picture.ts:399) | MET |
| Selected moment dot | `<circle r="7" fill="var(--data)">` at full opacity; selection overrides the nodal rendering | `<circle class="dot on" r="7">`, drawn before the nodal branch so selection overrides it (picture.ts:391-392) | MET |
| Shared-date cluster ring | `<circle r="7" fill="none" stroke="var(--data)" stroke-width="1" opacity=baseOp>`, once per date group holding more than one moment; opacity 0.35 w… | `.halo` `r=7`, `stroke:var(--data);stroke-width:1;opacity:0.35`, drawn once per date group holding more than one, dimmed when partly lit (picture.ts:341-350; theme.css:138) | MET |
| Lit-dot stacking | same date, multiple lit: y = 104 for the first when more than one is lit (else 99), 94 for the second, then `104 + 10*(i-1)`. Up to three stacked o… | `i===0 ? (lit.length>1 ? wire+5 : wire) : i===1 ? wire-5 : wire+5+10*(i-1)` (picture.ts:344) | MET |
| Leader line | `<line y1=99 y2=ROWS[i]+15 stroke="var(--data)" stroke-width="1" opacity="0.5">`, one per unique x, labels sorted by x and sliced to three, deduped… | `.ss-lead` 1px wide, `background:var(--data)`, `opacity:0.5`, from `ROWS[row]+15` down to the wire, deduped on `x.toFixed(1)` over rows already sliced to three (picture.ts:445-453; spotlight.ts:94; theme.css:154-159) | MET |
| Label row text | `400 13px/15px "IBM Plex Mono"`, colour `--ink`, height 15px; lit rows `color: var(--data); font-weight: 500`; meta rows `color: var(--faint)` | `.ss-t{font:400 13px/15px var(--mono);height:15px}`, `.on` `--data` weight 500, `.meta` `--faint` (theme.css:143-153) | MET |
| Label placement and budget | up to 3 rows; horizontal budget `min(44, floor((x1 - x - 4) / 7.8))` characters, left-aligned right of its dot; under 12 characters it flips to rig… | `rows()` matches the mockup's budget and flip, but returns early at `budget < 1` (spotlight.ts:109), and the leader is emitted inside the loop over the returned rows (picture.ts:446), so a dropped label also drops its leader | CHANGED |
| Year labels | `400 13px/17px "IBM Plex Mono"`, colour `--faint`, at top 136px, left edge and, if different, right edge | `.ss-yr` at `top:136px`, left and right, right omitted when both years match (picture.ts:361-366) | MET |
| Which moments light | the most recent coach bubble's chips carry `data-mo` with the event indices they name; those light. A chapter of 3 or fewer lights all; otherwise i… | `spotlight(eventIds)` is called with the events a coach chip names; there is no cap of three at this layer, the cap comes from `rows()` slicing to three (picture.ts:112-119; spotlight.ts:94) | PARTIAL |
| Selected-moment writeout | replaces the spotlight rows: row 0 is meta (`date · who`, faint), rows 1 and 2 are the wrapped label; wrap width `floor((x1-x0)/7.8)` characters pe… | meta row plus `wrap2` over two rows, clipped at `min(88, wide*2)` (picture.ts:411-426; spotlight.ts:41-50) | MET |
| Word-row format | `{dateText} · {who, if not the protagonist} · {label}`; date is the year alone when the fraction is under 0.002, else `Mon YYYY` | `{dateText} · {who if not protagonist} · {label}`; approximate dates say the year only, certain ones say the month (spotlight.ts:30-35,54-63) | MET |
| Undated shelf | undated items sit below the lanes and are never positioned; they exist, undated | A 44x44 `?` button past the right end of the wire when the record has shelf items (picture.ts:504-511) | MET |
| Undated shelf visibility | visible at the panel base, or behind a tap | not applicable (no pick to build) | N/A |
| Undated shelf chip | dashed border 1px `--unsure`, border-radius 7px, padding `6px 9px`; the row masked with `linear-gradient(90deg,#000 82%,transparent)` at the right… | Tapping the shelf opens a caption offering "Ask when" (main.ts:184) | MET |
| Full-picture escape hatch | header "‹ THE WHOLE PICTURE", range label "1990 — TODAY", hint "pinch · drag", hint "hold any mark to fix it", undated shelf peeking from the base | not applicable (no pick to build) | N/A |
| Freshness banner copy | extracting: "Updating the picture from your conversation…"; pending review: "New details from your conversation are waiting to be added."; chat ahe… | No freshness banner in web/src | MISSING |
| Pin label row, FD-362 | "Family time line" at the left, mono 13px uppercase, tracking .08em; the right span carries the picture's state text | `.pin-label` present, `400 13px mono`, uppercase, tracking .08em, state text at the right (index.html:24-27; theme.css:102-119) | MET |

## 5. Picture symbols — one row per symbol

| element | spec value | build value | status |
|---|---|---|---|
| Person, female | `<circle r="13" fill="var(--panel)" stroke=currentColor stroke-width="1.5">`, rising to 2.4 when a move overrides the stroke | Everyone is `<circle class="disc" r="17">`, `fill:var(--panel);stroke:var(--faint);stroke-width:1.6` (moves.ts:37,60-72; theme.css:183). Sex is never read | CHANGED |
| Person, male or other | `<rect width="24" height="24">` offset -12/-12, same fill and stroke rules | No rect glyph exists in moves.ts | CHANGED |
| Person, play-by-play pane A | disc r=17, fill `--card`, stroke `--mute` 1.6; initial `600 12px "IBM Plex Sans"` centred; name mono 9px `--mute`, letter-spacing .04em, at y = cy… | The disc, a `600 13px` initial and a `400 13px mono` name, drawn while a move or a coach view puts people on stage (moves.ts:60-72; picture.ts:508-512). Disc radius 17 matches; resolution 29 settles the timing | MET |
| Person name label, board | `<text y="-20" font-size="10.5">`, fill `--move` and weight 600 for the current mover, `--faint` and 400 otherwise | `.nm{font:400 13px var(--mono);fill:var(--faint)}` at `y + R + 32` (theme.css:185; moves.ts:69). Resolution 2 supersedes the ratified 10.5px board and 9px pane A sizes and applies the floor to picture text, so 13px is the value to hold. Do not shrink this | MET |
| Emotional field, rings | three `<circle cx cy r=24 fill=none class="A d" stroke-width="2.4" opacity="0">`, `r` animating 18 to 170 over 1.65s, begins staggered at 0s / .55s… | `field()` draws 2 static circles at `r = R+8+i*8`, so 25 and 33, `stroke:var(--move);stroke-width:1.2;opacity:0.4`. No `r` animation and no stagger (moves.ts:75-79; theme.css:200) | CHANGED |
| Tremble | `@keyframes tremble10`, ±2.5px falling to ±2px, active 2-28% of a 10s loop, still afterwards | `@keyframes tremble` exists, 1.2s linear infinite, five steps of ±2px, still from 45% (theme.css:234-240), and is applied through the `shake` class. Distance sets the actor to `still`, so the actor never trembles while exposed (moves.ts:264) | CHANGED |
| Wall | thick line `x1=105 y1=30 x2=105 y2=98`, `.A d`, stroke-width 6; `@keyframes oneslabb` slides it in from `translateX(-48px)` with opacity 0 to 1 bet… | `wall()` draws one straight `.mv-wall` path 52px long across the midpoint, `stroke:var(--ink);stroke-width:4` (moves.ts:100-116; theme.css:210). No push-in animation, and it is ink rather than the move green | CHANGED |
| Field shadow behind the wall | a per-instance `clipPath` with `clip-rule="evenodd"`, a rect minus an angled wedge (`M0 0 H230 V130 H0 Z M105 30 L105 98 L0 142 L0 -14 Z`), applied… | No clip path anywhere in moves.ts or theme.css. `field()` draws complete circles that pass straight through the wall (moves.ts:75-79,263-268) | MISSING |
| Pre-wall / post-wall gating | `@keyframes preA` opacity 1 to 0 by 26-30%; `@keyframes postA` opacity 0 to 1 rising at 38-42%; both 10s infinite | No before and after phases; the wall and the field are drawn together in one static frame (moves.ts:263-268) | MISSING |
| Authorship trace | dashed line `x1=57 y1=64 x2=102 y2=64`, `.A d`, stroke-width 1.6, `stroke-dasharray="3 5"`, opacity animating `0;0;.55;.55` on keyTimes `0;.4;.46;1… | `.mv-trace` from the actor to the wall's midpoint, `stroke:var(--move);stroke-width:1.2;stroke-dasharray:3 4` (moves.ts:112; theme.css:211) | MET |
| Distance | the wall drawing, alone | Wall plus field, actor class `still`, no strike (moves.ts:262-265) | PARTIAL |
| Cutoff, the actor | the actor keeps their sharp outline and their name throughout; they tremble while exposed and go still once sheltered. Nothing about them dashes, d… | `Move.Cutoff` sets the actor to `still faded` and the target to `faded`; `.node.faded .disc{stroke-dasharray:3 3}` and `.node.faded .nm, .node.faded .ini{opacity:0.55}` (moves.ts:266-273; theme.css:193-194). Both people visibly fade, against the ruling that the actor never disappears | CHANGED |
| Cutoff strike-through | `x1=92 y1=86 x2=118 y2=42`, `.A d`, stroke-width 3, gated by `postA` on a 10s loop | `.mv-strike` runs the full actor-to-target line rather than across the wall, `stroke:var(--ink);stroke-width:2` (moves.ts:108-110; theme.css:212). The actor is also given `faded`, which dashes their outline and drops their name to 0.55 opacity, against the ruling that the actor never disappears (moves.ts:266-273; theme.css:193-194) | CHANGED |
| Conflict, both figures | mover circle `cx=45 cy=55 r=14` `.A` with `buzz .28s infinite`; target rect `x=162 y=41 w=28 h=28` `.A` with `buzz .28s infinite reverse` | Both figures get `shake`, `tremble 1.2s` (moves.ts:275-277; theme.css:198) | MET |
| Conflict, sparks | one zigzag polyline `points="70,55 82,48 92,62 102,49 112,61 122,49 132,61 144,55"`, `.A d`, stroke-width 2.4; plus an 8-line radial spark cluster… | `sparks()` draws four separate 3-point zigzags stacked 9px apart at the midpoint, `stroke:var(--move);stroke-width:2`, static (moves.ts:352-364; theme.css:214). No single polyline, no radial spark cluster, no scale pulse | CHANGED |
| Toward, the walk | mover circle `cx=45 cy=55 r=14` `.A`, `@keyframes slide` translateX 0 to 96px at 50%, held to 94%, `8s ease-in-out infinite` | `steps` moves the actor 9px along the unit vector; the figure carries an SVG translate with no transition (moves.ts:228-234,50-53,62-64) | PARTIAL |
| Toward, the arrow | line `y1=55 x2=146 y2=55` `.A d` stroke-width 2.4 `stroke-dasharray="10 8"`, `flow 1s linear infinite`; nested `<animate>` on `x1` with values `62;… | `.mv-arrow` `stroke:var(--move);stroke-width:2.4;stroke-dasharray:240;animation:draw 0.6s ease-out forwards` between two fixed points (moves.ts:82-97; theme.css:201-208). The tail does not travel and the arrow never leaves | CHANGED |
| Away | mirror of toward: mover `cx=120 cy=60 r=14`, `awaywalk` translateX 0 to -68px between 50% and 94% over 8s; trailing line `.A d` stroke-width 2.4 `d… | Same arrow, drawn behind the mover at `R+46`, actor stepped -11px; it also stays drawn (moves.ts:236-243,88-92) | CHANGED |
| Projection, blur | an SVG filter, not a CSS one: `<filter id="pb" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="1.2"/></filter>`. A CSS `… | A CSS `filter: blur(1.2px)` on `.ss .node .ghost` (theme.css:186-192), applied wherever `figure()` is called with `ghost=true`, which is any figure classed `anx` (picture.ts:554). The ratified blur is an SVG `feGaussianBlur stdDeviation="1.2"` inside a filter region of -60% by 220% (move-language.html:181) — a near neighbour, not the same operation | PARTIAL |
| Projection, sharp selves | parent `cx=52 cy=50 r=15` `.A` stroke-width 2; child `cx=178 cy=92 r=11` `.A` stroke-width 2 | The `.disc` is always drawn under the ghost, for both people (moves.ts:60-72) | MET |
| Projection, ghost-double | the same circle inside the blur filter, `.A d` stroke-width 2, with `pshakeC 1.1s infinite`; parent opacity `1;1;0;0` and child opacity `0;0;1;1`,… | `.ghost` on both the parent and the child, both carrying `shake` (moves.ts:335-344; theme.css:186-192). Two deltas from the ratified mark: `stroke-width` is 2.4 against the ratified 2 (move-language.html:184,191), and the blur is the CSS filter rather than the SVG one. Do not read PARTIAL here as geometry already correct | PARTIAL |
| Projection, spike static | 8 lines `.A d` stroke-width 1.8, each with its own opacity flicker between 0.27s and 0.58s; the group scaling `1;1;.12;.12` on the parent and `.12;… | `spikes()` draws 10 static spikes from `R+3` to `R+10`, `stroke-width:1.6`, identically on both people at once (moves.ts:121-131,341; theme.css:213). No per-spike flicker and no inverse-linked gradient, so nothing shrinks on the parent as it sprouts on the child | CHANGED |
| Projection, flow arrow | `x1=68 y1=57 x2=156 y2=83` `.A d` stroke-width 2.8 `stroke-dasharray="9 7"`, `flow .45s linear infinite`; head `<polygon points="165,86 150,76 153,… | `.mv-flow` `stroke-width:2.4;stroke-dasharray:6 6;animation:drain 1.4s linear infinite` (moves.ts:186-191; theme.css:219-228). The flow lives in the dashes, at 2.4 and 6 6 rather than 2.8 and 9 7, on a 1.4s march rather than 0.45s | PARTIAL |
| Anxiety shake primitive | `pshakeC` / `cshakeC`, identical: `0%,100%(0,0) 20%(-2.5,1.5) 45%(2.5,-1.5) 70%(-2,1) 85%(2,-1)`, 1.1s infinite | One `tremble` keyframe shared by every shaking figure, 1.2s, five steps (theme.css:234-240) | PARTIAL |
| Anxiety variable | the projection rig on a single figure: sharp base `cx=115 cy=64 r=17` `.A` stroke-width 2.2 always present; ghost-double with its own blur filter a… | The standalone anxiety shift draws `field(actor) + spikes(actor)` (moves.ts:210-215), so it adds the two emotional-field rings that belong to distance and cutoff. The ghost and shake are right | CHANGED |
| Overfunctioning | dominant circle `cx=88 cy=64 r=15` `.A`, `domup 3s ease-in-out infinite` translateY 0 to -5px; UP flank arrow shaft `x1=60 y1=76 x2=60 y2=54` plus… | `flank(actor, true)` plus a down flank on the target, actor class `f-up`; no rise or sink, since the move returns no steps (moves.ts:316-319) | PARTIAL |
| Underfunctioning | submissive rect `x=128 y=50 w=28 h=28` `.A`, `subdown 3s ease-in-out infinite` translateY 0 to +5px on the same beat, opposite phase; DOWN flank ar… | Mirror of the above, actor class `f-down`, again with no movement (moves.ts:320-323) | PARTIAL |
| Flank arrow size | shaft about 22px against a 15-17px main-mark radius, which reads as ~60% size. Reduced to half or two-thirds of the first attempt | Shaft from `person.y-11` to `person.y+11`, so 22px against a 34px person, `stroke-width:2.2` (moves.ts:166-176; theme.css:217) | MET |
| Triangle, inside | target rect `x=118 y=36 w=26 h=26` static; mover circle r=13 with `cx` `100;100;58;58` and `cy` `49;49;56;56` on keyTimes `0;.2;.55;1` over 8s; dis… | Actor steps 14px toward the target and the third person is pushed 16px outward, with an arrow drawn (moves.ts:294-306). The mover never overlaps the one they want | PARTIAL |
| Triangle, outside | two static corners: circle `cx=88 cy=40 r=13`, rect `x=128 y=27 w=26 h=26`; two tension zigzags `points="104,84 100,76 106,68 98,60 103,52"` `.A d`… | `tension()` draws straight dashed lines from the mover to both others, `stroke:var(--move);stroke-width:1.6;stroke-dasharray:4 4` (moves.ts:178-184; theme.css:218), plus an away arrow and a -13px step. The ratified mark is an animated zigzag polyline that clears with the walk; here the tension is drawn in the same frame as the walk | CHANGED |
| Fusion | person A circle `cy=64 r=15` with `cx` `70;70;101;101`; person B rect `y=50 w=28 h=28` with `x` `140;140;112;112`, both on keyTimes `0;.2;.55;1` ov… | `bands()` draws three concentric ellipses around the pair's midpoint, `rx` growing 0/5/10 from `|dx|/2+R+10`, `stroke-width:1.4;opacity:0.6` (moves.ts:145-160; theme.css:216). The ratified mark is three straight horizontal lines at y offsets -6/0/+6 at stroke-width 2.4-2.6 that shrink as the pair approach; nobody approaches here and no shared-field ring is drawn | CHANGED |
| Defined self, actor | circle `cx=42 cy=64 r=15`; ink phase `.A` stroke-width 2.2 with opacity `1;1;0;0` at keyTimes `0;.375;.385;1`; green phase, same geometry, `stroke=… | `.node.self .disc{stroke:var(--move);stroke-width:2.6}` from the first frame (moves.ts:279-285; theme.css:195). No ink phase and no swap at the moment of stillness | CHANGED |
| Defined self, the storm | other party rect `x=172 y=50 w=28 h=28` with `btrem2 12s infinite`; two long storm rings `r` 18 to 170 over 1.1s (second `begin=".55s"`), opacity `… | No storm rings anywhere in moves.ts or theme.css | MISSING |
| Defined self, clear ring | `cx=42 cy=64 r=20 stroke="var(--self)" stroke-width="2.4" opacity="0"`, `r` 18 to 120 over 2s, `begin="3.2s;11.2s"`, opacity `.95;0` | One static `.mv-clear` at `r = R+12`, `stroke:var(--move);stroke-width:1.6;opacity:0.7` (moves.ts:283; theme.css:215). Not animated and not delayed | CHANGED |
| Symptom cross | `translate(146,60)` with two `<rect class="df" rx="1">`, `x=-8 y=-3 w=16 h=6` and `x=-3 y=-8 w=6 h=16`, filled solid green | `cross()` draws a `.sym-bg` disc `r=9` filled `--panel` with a 2px `--move` ring, carrying a `.sym-x` plus of two 8px strokes at `stroke-width:2.2` (moves.ts:134-151; theme.css:229-230). The ratified mark is two filled rects, 16x6 and 6x16, with no disc behind them | CHANGED |
| Symptom up arrow (worse) | shaft `x1=172 y1=74 x2=172 y2=48` `.A d` stroke-width 2.6, head `<polygon points="172,42 164,52 180,52" class="df">`; opacity `0;0;1;1;0;0` on keyT… | `.mv-dir` chevron, `stroke-width:2`, drawn beside the disc (moves.ts:138-141; theme.css:231). Not a 2.6 shaft with a filled polygon head, and it does not alternate on an 8s cycle | CHANGED |
| Symptom down arrow (better) | shaft `x1=172 y1=48 x2=172 y2=74` `.A d` stroke-width 2.6, head `<polygon points="172,80 164,70 180,70" class="df">`; opacity keyTimes `0;.5;.56;.9… | Same chevron mirrored (moves.ts:137-140) | CHANGED |
| Functioning | one circle `cx=115 cy=64 r=17 fill=none stroke-width="2.6"`; `stroke-dasharray` animating `106 0; 106 0; 5 6; 5 6; 106 0; 106 0` on keyTimes `0;.12… | Two static classes: `.node.f-down .disc{stroke-dasharray:5 4;stroke:var(--faint)}` and `.node.f-up .disc{stroke:var(--move);stroke-width:2.4}` (moves.ts:216-221; theme.css:196-197). The semantics are right, the animated break from solid to dashes is not built | PARTIAL |
| Nodal moment mark | double ring: `<circle r="6.5" fill="none" stroke="var(--data)" stroke-width="1.5">` plus a solid `<circle r="2" fill="var(--data)">` core | `<circle class="dot nodal" r="6.5" stroke-width="1.5">` plus `<circle class="dot core" r="2">`, on cutoff, defined-self, fusion, or two or more targets (picture.ts:393-397; theme.css:136-137) | MET |
| Anxiety spikes, generic generator | `gSpikes`: stroke-width 1.6, opacity animating `0;1;.2;1;0` over 0.3-0.75s staggered per spike, n spikes between radius r+2 and r+2+l where l = 6 +… | Replaced by `spikes()` (moves.ts:121-131) | CHANGED |
| Directed arrow, generic generator | `gArrow`: dashed line stroke-width 2.4, `stroke-dasharray: 8 6`, `gflow .5s linear infinite`; polygon head; optional ride translate over 1.2s with… | Replaced by `arrow()` (moves.ts:82-97) | CHANGED |
| Conflict zigzag, generic generator | `gZig`: polyline stroke-width 2.2, segment count `max(4, round(L/13))`, `gsparkp .5s infinite` scaling .75 to 1.1 | Replaced by `sparks()` (moves.ts:352-364) | CHANGED |
| Wall, generic generator | `gWallPair` / `gWallSolo`: wall bar stroke-width 4.5 paired or 4 solo; ripple circles stroke-width 2 animating r 16 to L*0.9 over 1.5s, the second… | Replaced by `wall()`; no ripple rings and no solo variant (moves.ts:100-116) | CHANGED |
| Fusion, generic generator | `gFusion`: three parallel lines at y = -6, 0, 6, stroke-width 2.4 | Replaced by `bands()`, which draws ellipses rather than three parallel lines (moves.ts:145-160) | CHANGED |
| Ring, generic generator | `gRing`: stroke-width 2.2, r animating `16;16;80;80` over 8s, opacity `0;.9;0;0`, `begin=".8s"` | Replaced by the static `.mv-clear` circle (moves.ts:283) | CHANGED |
| Flank, generic generator | `gFlank`: two lines forming a chevron, stroke-width 2.2, `animateTransform` bobbing `4*sign` over 3s infinite | Replaced by `flank()`; a chevron on a shaft, no bob animation (moves.ts:166-176) | CHANGED |
| Move colour | one green for every move mark, `--move` / `MV` | Every `.mv-*` class is `var(--move)` except `.mv-wall` and `.mv-strike`, which are `var(--ink)` (theme.css:200-231) | PARTIAL |
| Symbol legibility rule | symbols must be self-evident without a legend, and each move must be apparent in the drawing itself. A text label is not enough; cutoff must show w… | — | UNCHECKED |
| Symptom badge, playbyplay variant | circle r=7.5 offset (+14,-14), fill `--amber-line`; "!" `700 10px "IBM Plex Sans"` fill `#1a1200`; `pop .5s cubic-bezier(.2,1.6,.4,1)` scale .2 to 1 | not applicable (conflict with no pick) | N/A |
| Anxiety ring, playbyplay variant | two concentric rings at r = R+7 = 24, stroke `--amber-line` 2.2 opacity .85, `pulse 1s ease-out` twice, scale .75 to 1.35, opacity 1 to .15 | not applicable (conflict with no pick) | N/A |
| Cutoff, playbyplay variant | `.cutline` stroke `--mute` 1.6 round cap drawn over 500ms; after 480ms two 8px diagonal slash ticks stroke `--ink` 2.2 pop in at the midpoint ±4px;… | The build fades the actor and the target after a cutoff, which follows the play-by-play drawing rather than the ratified ruling (moves.ts:266-273) | CHANGED |
| Drawability tick | `.tick` stroke `--ink` 1.5-2px; a moment with no direction | Not drawn anywhere in picture.ts | MISSING |
| Drawability dot | `.dot` fill `--draw`, r 3.2px; a directed moment, up or down | `.dot` fill `--data` on the wire (theme.css:135) | MET |
| Step line | `.step` stroke `--draw` 2.2, round cap; drawn only when the directed-point threshold is met, spanning only where points exist | No step line in picture.ts | MISSING |
| Uncertainty band | `.band` fill `rgba(201,148,65,.30)` light / `rgba(216,168,83,.26)` dark; zoomed or secondary `.bandZ` at .20-.22 | No band for a guessed date. An approximate date says its year in words instead (spotlight.ts:30-35) | MISSING |
| Gap / silence | dotted line, stroke `--muted` 1.6, `stroke-dasharray: 1.5 5`, opacity .55 | No dotted gap segment in picture.ts | MISSING |
| Recorded no-change | `.flat` stroke `--ink` 2.5, round cap | No flat mark in picture.ts | MISSING |
| Open-ended range fade | gradient stops, stop-opacity .5 to 0, colour `--draw` | No gradient or fade in theme.css | MISSING |
| Ordering between guesses | order is drawn only when the guess ranges do not touch (1994±1 against 1996±1 draws it; two "1992" guesses sit side by side with none) | Not drawn. Order questions surface as an amber `?` instead (picture.ts:489-501) | MISSING |
| Amber question glyph | 13x13px circle, border `1.3px solid var(--unsure)`, `500 9px mono`; `@keyframes ask` opacity .55 to 1, 2.8s ease-in-out infinite; off under reduced… | `.qm{fill:var(--ask);font:500 15px var(--mono)}`, 13px in the small variant (theme.css:178-179). Resolutions 16 and 24 settle on the converged system's amber text mark rather than the editorial family's 13x13 outlined circle, so this matches; it does not pulse | MET |
| Trace highlight on a bubble | `outline: 2px solid var(--move)`, offset 2px, `tracefade 2.2s ease-out forwards`, holding solid through 40% then fading to transparent | No `traced` class or outline animation in theme.css | MISSING |
| Abstract people-mapping | rejected. If the visual maps people it IS the family diagram, or a subset showing the movement between people: Bowen's chalkboard, sequence on the… | People are only ever drawn as the cast of a move or a coach view (picture.ts:508-560) | MET |
| Chapter Shelf list-row glyph set | compact glyphs: vertical tick plus circle for single-actor moves; bowing polylines for toward and away; one zigzag for conflict; two segments with… | not applicable (no pick to build) | N/A |

## 6. Chalkboard / moves board

| element | spec value | build value | status |
|---|---|---|---|
| The three levels | resting wire 78px → chapter 158px → moves board 264px, one continuous zoom, one visual language; the claims live in chat | One picture, two heights (picture.ts:41,283-285) | CHANGED |
| The middle level, tap-zoom cluster | CUT. Tapping a cluster is point-and-ask; the cluster's words live in the chat via the play-by-play, never in a navigable data view. The move step-t… | Correctly absent; no zoom-into-a-cluster path in picture.ts | MET |
| Board height, phone | 264px, viewBox `0 0 380 264` | `STAGE_H = 252` (picture.ts:41) | CHANGED |
| Board layout, phone | centre (190,132); people on a ring of radius R=82, angle `-π/2 + i*2π/n`, x radius `R*1.75` and y radius `R` | `ring()` radius `min(78, max(46, width/2 - 74))`, y flattened to 0.62, start angle `-π/2`, centre y `STAGE_H-59-96` (moves.ts:349-366; picture.ts:42,517) | CHANGED |
| Board layout, desktop original | viewBox `0 0 840 290`, centre (420,145), ellipse radius 180 across by 100 down, ordered by bond adjacency | not applicable (no pick to build) | N/A |
| Pair-bond lines | stroke `--line`, stroke-width 1.2, drawn first, beneath everything | No bond lines drawn on stage (picture.ts:508-560) | MISSING |
| History marks | earlier moves stay on the board at `opacity: 0.16`, behind the current gesture; they fade in over `.32s ease` from 0 | Only the current move is drawn; nothing is left behind (picture.ts:521-545) | MISSING |
| Gesture glow filter | `<filter><feGaussianBlur stdDeviation="1.1"/></filter>` | No feGaussianBlur filter; the ghost uses a CSS blur instead (theme.css:191) | CHANGED |
| Current-mover emphasis | mover label fill `--move`, weight 600; every other label fill `--faint`, weight 400 | No mover emphasis on the name; every `.nm` is `--faint` (theme.css:185) | MISSING |
| Board nav, back | `←` in the top-left corner slot | No board and no back control | MISSING |
| Cluster-view close | `✕` in the top-right corner slot at level 2 | No cluster level to close | MISSING |
| Board step controls | `◀` plain `.btn` and `▶ next move` `.btn.primary`, min-height 44px, padding `0 14px`, border-radius 4px | No step, back or next control. A sequence view auto-advances on a timer (picture.ts:180-185) | MISSING |
| Board entry button | `▶ watch the N moves`, `.btn.primary` with `border-color: var(--data); color: var(--data)`; base `.btn` is `500 12px "IBM Plex Mono"`, padding `6px… | A `.btn.play` reading "Play" in the caption row, `min-height:36px` (main.ts:189; theme.css:429-442) | CHANGED |
| Board caption | `13px`, min-height 15px (20px in drilldown), reading `step/total · year — from → to · label`, plus a trace chip back to the coded chat message | No step-number caption. The caption row holds an ask chip and Play (main.ts:184-191) | MISSING |
| Zoom into a chapter | SVG `transform: scale(min(4, viewBoxWidth/boxWidth))`, `transition: transform .6s cubic-bezier(.4,0,.2,1), opacity .6s`, opacity to 0.25, level swa… | No zoom transition in picture.ts | MISSING |
| Vertical space | too much is wasted in the zoomed-out timeline and the zoomed-in cluster views. Only the play-by-play may expand, because it is graphics-rich | — | UNCHECKED |
| The crowded chapter view | rejected on font size and label collision in dense clusters; surgical fixes will not do, the view needs rethinking | Correctly absent | MET |
| The chalkboard replaces the heat map | numbered moves on a subset of the full diagram, one tap from the wire | No heat map, and no chalkboard level either (picture.ts) | PARTIAL |
| Episode-open lanes | two lanes only, the subject's plus the one the correlation needs; amber threads tie correlated moments; an uncertainty band ends where a question r… | No lanes in picture.ts | MISSING |
| Wire at rest, composite | viewBox `0 0 760 70`; caption "Three episodes, one count chip, one amber question. Nothing else until you ask." | One wire with dots and an amber question mark (picture.ts:325-355,489) | MET |
| Chalkboard, composite | viewBox `0 0 760 150`; numbered moves on the diagram subset | No numbered moves and no diagram subset | MISSING |
| Pairs, face to face | two moments side by side, a question mark between them, no axis | The compare view calls `spotlight([a, b])`, which lights both on the one wire (picture.ts:176-178) | MISSING |
| Bands under the wire | quiet horizontal bands beneath the main wire, start and end dated, ending where dots pile up | No relationship-span bands (picture.ts) | MISSING |
| Braid, two rails | two parallel rails, self and other, with correlation ties | not applicable (superseded) | N/A |
| Constellation / Chapters | named episode groupings, no axis in the Chapters variant; drift rightward through years in Constellation | Chapters carry their own labels and drive the focus and the bracket (picture.ts:229-231,463-475) | PARTIAL |
| Other divergent picture concepts | comic strip, tree rings, one bond one thread, words sized by frequency, year wheel, mobile, story spine, seismograph, question horizon, walked path | not applicable (no pick to build) | N/A |
| Close-up triangle drawings and cluster vignettes | explicitly LATER | Correctly deferred; the triangle view draws the plain ring (picture.ts:546-558) | MET |
| Section numbering in mockups | sections and boxes in mockups must be numbered so they are easy to refer to | not applicable (no pick to build) | N/A |

## 7. Show-tool view kinds

| element | spec value | build value | status |
|---|---|---|---|
| `triangle` — a triangle over three people | no mockup fixes the geometry | `ViewKind.Triangle` sets the cast and marks the picture closed; with exactly three figures it draws dashed `.mv-tension` lines around all three on the same circular ring (picture.ts:164-169,546-558) | PARTIAL |
| `span` — a span over a time range | no ruled drawing; the as-built draws a filled band at 14% opacity | `ViewKind.Span` sets a band; `.span` is a rect at `wire-14`, height 28, `rx 6`, `fill-opacity:0.14` (picture.ts:170-174,477-484; theme.css:140) | PARTIAL |
| `compare` — two moments compared | no mockup. The nearest approved drawing is "Pairs, face to face": two moments side by side, a question mark between them, no axis | `ViewKind.Compare` calls `spotlight([event_a, event_b])` and nothing else; the comparison itself is never drawn (picture.ts:176-178) | PARTIAL |
| `sequence` — a sequence of moves | the moves board, stepped in order | `ViewKind.Sequence` steps each event and awaits `SEQUENCE_MS = 1100` (picture.ts:32,180-185). No step controls | PARTIAL |
| `cluster` — a cluster view | resolves a chapter by id or cluster id and spotlights its events; the parameters resolve against the record or the call fails by name | `ViewKind.Cluster` resolves a chapter by id or cluster id and spotlights its events (picture.ts:186-196). Resolution 34 keeps it as unruled rather than ruled in, so it is working code awaiting a decision, not a defect | NEEDS-OWNER |
| Parameter validation | missing parameters raise by name; every person and event id is checked against the record before a view is built | — | UNCHECKED |
| Extensibility | adding a kind must be easy; each kind added must show something meaningful | A kind must be added to the `ViewKind` enum and the `View` union (types.ts) and to the switch in `show()` (picture.ts:159-197), besides the backend | PARTIAL |

## 8. Play-by-play

| element | spec value | build value | status |
|---|---|---|---|
| Authorship | coach-authored: the moves are data and animate deterministically; the coach writes the words around them, picks which moves and in what order, make… | The picture only ever draws from a coach turn or the Play action; `step()` is driven by the events a reply names (picture.ts:155-158; main.ts:202-213) | PARTIAL |
| Priority | the play-by-play is where the value is. Fix timing and symbol gaps before adding anything; close-up triangles and eventually the family diagram com… | — | UNCHECKED |
| Owner's verdict on the coded version | "looks and feels great, that is what I wanted" | — | UNCHECKED |
| Pinned picture region | background `--card2`, border-bottom 1px `--rule`, padding `10px 12px 4px`. A FIXED region above the chat | `.pic{flex:none}` keeps it out of the scroll, but its height changes between 158 and 252 (theme.css:101; picture.ts:285) | PARTIAL |
| Picture SVG | `viewBox="0 0 440 262"`, `width:100%; height:auto` | One SVG sized to the picture's own width and height, not the pane A stage (picture.ts:322) | CHANGED |
| People on stage | five people permanently on stage at fixed coordinates, disc r=17, 12px initial, 9px mono name 30px below | `stage()` returns an empty string unless a move is playing or a coach view sets a cast (picture.ts:508-514), which is what resolution 29 asks for | MET |
| Time axis | stroke `--rule` 1.4, full width at y=222 from x=30 to x=424; ticks at 1985, 1995, 2005, 2015, 2025; year labels `"IBM Plex Mono"` 9px fill `--mute` | No axis, ticks or year labels along a stage (picture.ts) | MISSING |
| Density blobs | ellipses at three points, rx `[6,10,7]`, ry = rx × 0.68, fill `--idle` | Not drawn | MISSING |
| Focus blob | fill `--teal` at opacity .28, rx=27 ry=9; `.flash` at opacity .6 reverting after 900ms | Not drawn; the focus is a bracket outline instead (picture.ts:463-475) | CHANGED |
| Move dots on the axis | r=3.4 fill `--idle`; once played, r=4.6 fill `--teal`, `transition: fill .3s, r .3s`; `.flash` fill `--amber` | The wire's own dots stay under the stage, but they carry no played state (picture.ts:336-355) | PARTIAL |
| Cluster bracket and label | bracket stroke `--teal` 1.2; label mono 9px fill `--teal-ink`, letter-spacing .04em, e.g. "1993–1997" | `.brk` path drawn with no text label at all, and only when no words are on the picture (picture.ts:463-475; theme.css:139). The label is missing rather than mis-sized; at the resolved 13px it needs room the bracket may not have | PARTIAL |
| Node move transition | `transition: transform .55s cubic-bezier(.4,1.3,.5,1)` — an overshoot ease | The figure is translated by an SVG transform attribute with no CSS transition on `.node` (moves.ts:62-64; theme.css:183-198) | PARTIAL |
| Node pop-in | `@keyframes pop` scale .2 to 1, opacity 0 to 1, `.5s cubic-bezier(.2,1.6,.4,1)` | No pop keyframe in theme.css | MISSING |
| Move arrow | `fill:none; stroke:var(--teal); stroke-width:2.4; stroke-linecap:round`; drawn in over 600ms ease-out; arrowhead marker `viewBox="0 0 10 10" refX="… | `stroke-dasharray:240` with `draw 0.6s ease-out forwards`, marker head `refX 8.5 refY 5 markerWidth 5.5` (picture.ts:323-325; theme.css:201-208) | PARTIAL |
| Chat log region | padding 14px, flex column, gap 11px, min-height 214px — the GROWING region below the fixed picture | `.chat{flex:1;min-height:0;overflow-y:auto}` is the only scrolling region on the chat screen (theme.css:256-265) | MET |
| Coach typing speed | 2 characters then an 18ms sleep, about 9ms per character; the closing ask line at 16ms per 2 characters | — | UNCHECKED |
| Per-move narration hold | 1000ms after each chip or move before the prose continues | `SEQUENCE_MS = 1100` between steps (picture.ts:32), which resolution 21 keeps as the ruled one-beat-per-move advance | MET |
| Offer-chip stagger | 160ms between each of the three answer chips | No stagger; offered chips render with the bubble (chat.ts:55-71) | MISSING |
| Initial coach delay | 320ms before typing starts, 260ms before the ask line | `await wait(300)` before the first-run greeting types (main.ts:289) | CHANGED |
| Typing caret | 2px by 1em bar, background `--teal`, `@keyframes blink .7s steps(1) infinite` | `.bub.typing::after` a 2px by 1em bar on `blink 0.7s steps(1) infinite`, plus `.bub.dots` three 6px dots on `bounce 1s` staggered .15s and .3s (theme.css:287-334) | MET |
| Ask prompt line | `margin-top: 9px`, colour `--amber`, weight 500 | Offered chips render as `.chip.ask` with literal square brackets, amber border, radius 8 (chat.ts:58-64; theme.css:374-380). There is no separate amber ask line | PARTIAL |
| Composer field, play-by-play | min-height 34px, border 1px `--rule`, radius 10px, padding `7px 10px`, font-size 13.5px, background `--card2`; focus `outline: 2px solid var(--teal)` | `.field` contenteditable, min-height 44, max-height 140, radius 22, `400 17px` (index.html:33-34; theme.css:391-405) | CHANGED |
| Send affordance, play-by-play | mono 11px, letter-spacing .09em, colour `--mute`, uppercase — plain text, not a button graphic | `.send` 44x44 circle, `--data` background, up arrow (index.html:35; theme.css:406-416) | CHANGED |
| Beat length, as built | 1400ms in chat-first-app, 1100ms in FD-362 | 1100ms per step (picture.ts:32); nothing loops for 8s | CHANGED |
| Chip lights while its move draws | `LIT_MS = 1000` | `LIT_MS = 1000`; `.chip.lit` turns amber on `--ask-tint` (chat.ts:19; theme.css:367-371) | MET |
| Play triggers a fresh coach turn | `playThrough(clusterId)` calls the play endpoint, types the reply, and steps the picture per named event | The Play action calls the play endpoint and steps the picture per named event (main.ts:194-199,202-213) | MET |
| Pane B, app-generated record | tape region border-bottom 1px `--rule`, background `--card`, padding `11px 13px 13px`, mono 12px, min-height 132px; header 9.5px uppercase; one fla… | Correctly absent | MET |

## 9. Chips

| element | spec value | build value | status |
|---|---|---|---|
| Chips are the primitive | a chip is a reference into the record — an event, a cluster or a person — rendered in both coach and user messages | Chips render in coach and user messages; a tap drops the reference into the composer as a token (chat.ts:29-52; caption.ts:213-226) | MET |
| Two taps on the picture | the first tap looks: a title or caption, free, nothing enters the chat. The second tap is a chip and speaks | `reduce()` records a Look on the first tap and a Say only on the chip tap (caption.ts:198-226) | MET |
| Coach-placed inline chips | tappable chips inside coach prose that jump to a cluster or a set of events | A coach chip aims the picture through `aimedEvents()` (chips.ts:117-137) | MET |
| Base chip, converged files | `display:inline-block; font:500 13px "IBM Plex Mono"; color:var(--data); border:1px solid var(--data); border-radius:10px; padding:1px 8px; margin:… | `.chip{font:500 13px/22px var(--mono);border-radius:13px;padding:1px 10px;margin:2px 4px 2px 0;background:none}` with no border unless it is `.data` or `.ask` (theme.css:339-379) | CHANGED |
| Base chip, earlier files | the same shape at `500 11px mono` | not applicable (superseded) | N/A |
| Chip data attributes | `data-aim="{chapterIndex}" data-mo="{comma-separated event indices}"` | `data-kind`, `data-target`, `data-full` on the button (chat.ts:60-62). The picture reads the chip through `aimedEvents`, not a `data-mo` attribute | CHANGED |
| Chip markup, server side | `[[kind:target\ | `[[kind:target|label]]` parsed client-side by `tokenize()`; `range` narrows to null so it stays plain words rather than a chip that goes nowhere (chips.ts:14-40,86-110) | PARTIAL |
| Chip payload by kind | chapter → `cluster_id`; events → `event_ids`; person → `person_id`; range → `start` and `end` as ISO dates | Four markup kinds narrow to three chip kinds plus `ask`: event, cluster, person (chips.ts:27-35) | PARTIAL |
| Trace chip ("coded in") | `.chip` reading `coded in: <title, truncated at 30 chars> · <short date> →`, carrying `data-sid` and `data-bi` | No coded-in chip in web/src | MISSING |
| Data chip, play-by-play | `font:500 12.5px/1.25 "IBM Plex Sans"; display:inline; padding:2px 8px; border-radius:999px; background:var(--teal-soft); color:var(--teal-ink); bo… | `.chip.data{color:var(--data);border:1px solid var(--data)}` — an outlined pill, not a filled teal-soft pill with an inset ring (theme.css:372) | CHANGED |
| Lit chip | background `--amber-soft`, colour `--amber`, inset ring `--amber-line` | `.chip.lit{color:var(--ask);border-color:var(--ask);background:var(--ask-tint)}` (theme.css:367-371) | MET |
| Offer / ask chip | `background:transparent; color:var(--amber); box-shadow: inset 0 0 0 1px var(--amber-line); border-radius:8px; font:"IBM Plex Mono" 11.5px; padding… | `.chip.ask` amber, radius 8, no background, wrapped in literal square brackets (chat.ts:63; theme.css:374-380) | MET |
| Token pill in the composer | `font:"IBM Plex Mono" 11.5px; background:var(--amber-soft); color:var(--amber); box-shadow: inset 0 0 0 1px var(--amber-line); border-radius:6px; p… | A tapped chip is inserted into the composer as a chip button, removable by tapping it again (chat.ts:33) | PARTIAL |
| Chip inside a user bubble | `color: var(--onaccent); border-color: currentColor` | `.bub.user .chip{color:var(--onaccent);border-color:currentColor}` (theme.css:381) | MET |
| Chip height | the as-built chips are 26px tall, under the 44px tap floor; the approved mockup draws them at about 21px. A 44px target inside flowing prose cannot… | Visual box is 22px line plus 2px padding plus a 1px border on `.data`/`.ask`, so 26px; `.chip::before{inset:-9px -4px}` grows the target to 44px (theme.css:339-360). A chip with no tone class has no border and its target is 42px | PARTIAL |
| Chip clip then fire | an over-long label shows clipped with an ellipsis; the first tap un-clips it, the second fires | `chipText` cuts at `CHIP_MAX = 34` at a space; the first tap un-clips, the next fires (chips.ts:62-78; chat.ts:36-40) | MET |
| Chip tones, as built | `.data` teal border; `.ask` amber border, radius 8, literal square brackets, no background; `.lit` amber text and border on `--ask-tint` | `.data`, `.ask`, `.lit` (theme.css:367-380) | MET |
| Historical coach messages | carry no chips; references only come back on a live reply | — | UNCHECKED |
| Count chip | opens on tap to reveal a dense episode's contents | No count chip; density shrinks the dot instead (spotlight.ts:66-68) | MISSING |
| Inline links instead of chips | `.ilink` colour `--draw`, dotted underline, underline-offset 2px | not applicable (no pick to build) | N/A |
| Undated "no date yet" chips doing nothing on tap | — | The shelf hit opens a caption offering "Ask when" (picture.ts:504-511; main.ts:184) | MET |

## 10. Chat bubbles and layout

| element | spec value | build value | status |
|---|---|---|---|
| Layout contract | the picture region is fixed at its level's height; the chat fills what is left and is the only thing that scrolls; the caption slot below the pictu… | The picture's height changes with the stage and the caption is toggled with `hidden`, so both push the chat (picture.ts:285,377; main.ts:173-185) | CHANGED |
| Caption minimum height | `min-height: 15px`, `margin-top: 4px`, `font-size: 13px` | No `min-height` on `.caption` (theme.css:247-252) | MISSING |
| Chat scroll region | `flex:1; overflow-y:auto; padding:14px 12px; display:flex; flex-direction:column; gap:10px; background:var(--bg); transition:opacity .15s` | `.chat{flex:1;min-height:0;overflow-y:auto;display:flex;flex-direction:column;gap:10px;padding:14px 12px;background:var(--bg)}` (theme.css:256-265). No `touch-action`, no `overscroll-behavior`, no drag handler | PARTIAL |
| Bubble base | `max-width:82%; padding:9px 12px; border-radius:14px; font-size:16px; line-height:1.45` | `.bub{max-width:84%;padding:9px 12px;border-radius:14px;font:400 17px/1.45 var(--sans);white-space:pre-wrap;overflow-wrap:anywhere}` (theme.css:266-274). 84% rather than 82%, and 17px, which meets the binding body floor the mockup's 16px missed | CHANGED |
| Bubble base, earlier files | the same shape at `font-size: 14px` | not applicable (superseded) | N/A |
| Coach bubble | background `--panel`, border 1px `--line`, `align-self: flex-start`, `border-bottom-left-radius: 4px` | `background:var(--panel);border:1px solid var(--line);align-self:flex-start;border-bottom-left-radius:4px` (theme.css:275-280) | MET |
| User bubble | background `--data`, colour `#fff`, `align-self: flex-end`, `border-bottom-right-radius: 4px` | `background:var(--data);color:var(--onaccent);align-self:flex-end;border-bottom-right-radius:4px` (theme.css:281-286) | MET |
| User bubble, hardcoded hex | `background: #0e7d78` written literally instead of `var(--data)` | Tokenised; no literal hex outside the `:root` blocks (theme.css:3-47,281-286) | MET |
| User bubble, translucent variant | `--bubu` = `rgba(20,108,124,.10)` light / `rgba(92,180,194,.14)` dark | not applicable (superseded) | N/A |
| Speaker label | `.who` mono `500 13px`, uppercase, letter-spacing .1em, colour `--faint`, 4px below | `.bub .who{font:500 13px/1.2 var(--mono);letter-spacing:0.1em;text-transform:uppercase;color:var(--faint);margin-bottom:4px}` (theme.css:307-313) | MET |
| System line | `.sys` centred, `500 13px/1.35 mono`, colour `--faint`, max-width 92%, single-line ellipsis | No `.sys` class in theme.css. Edits render as `.did` lines inside the coach's own bubble instead (theme.css:315-331) | CHANGED |
| Day divider | centred, 9.5px mono, letter-spacing .12em, colour `--muted` | not applicable (no pick to build) | N/A |
| Traced bubble | `outline:2px solid var(--move); outline-offset:2px; animation: tracefade 2.2s ease-out forwards` | No traced outline or `tracefade` in theme.css | MISSING |
| Input bar | padding `10px 12px`, border-top 1px `--line` | `.inbar{display:flex;gap:8px;align-items:flex-end;padding:8px 10px calc(8px + env(safe-area-inset-bottom));border-top:1px solid var(--line)}` (theme.css:383-390) | MET |
| Text input | height 44px, border-radius 18px, padding `0 16px`, `16px "Libre Franklin"`; a text field is 44 high with a 17px value and 16px side padding | `.field` min-height 44, radius 22, padding `9px 16px`, `400 17px/1.4`, focus border `--data` (theme.css:391-405). Meets the ruled 44 high and 17px value | MET |
| Send button | height 44px, min-width 44px, border-radius 22px, background `--data`, glyph "↑" | 44x44, radius 22, `--data` background, `600 19px` up arrow (theme.css:406-416) | MET |
| Send button, FD-360 | 34x34px | not applicable (superseded) | N/A |
| Composer, multi-line | a `contenteditable` div with `role="textbox"`, min-height 44px, max-height 140px; Enter sends, Shift+Enter makes a newline | contenteditable div with `role="textbox"`, min-height 44, max-height 140 (index.html:33-34; theme.css:391-395) | MET |
| Typing indicator | three 6px dots on `bounce 1s infinite` staggered .15s and .3s; a 2px cursor on `blink .7s steps(1) infinite` | Three 6px dots on `bounce 1s` staggered .15s and .3s, plus a 2px caret on `blink 0.7s steps(1)` (theme.css:287-334) | MET |
| Edit-summary line | `.did` one line per edit, mono 13px `--faint`, with a 6px `--move` dot bullet | `.did{font:400 13px/1.5 var(--mono);color:var(--faint)}` with a 6px `--move` dot bullet (theme.css:315-331) | MET |
| First-run greeting | "I'm here whenever you want to think out loud about your family. Tell me who is on your mind." | Typed after `wait(300)` when there are no prior statements (main.ts:289-294) | MET |
| Empty chat copy, FD-360 | "Say hello — the picture above fills in as you talk." | not applicable (superseded) | N/A |
| No modes | one agent. Coaching, app help, corrections and journaling all route from context, never from a user-visible switch | No mode switch in web/src; one chat surface plus the menu (index.html:22,39) | MET |
| Conversation drives everything | the UI is secondary; it fills gaps proactively, or the coach aims it via an inline chip | The picture only draws from a coach turn or the Play action (main.ts:202-213; picture.ts:112-119) | MET |
| Demo chat timing | next bubble after 1500ms if the previous sender was the coach, 900ms if the user; sends within 1200ms of the last are ignored | not applicable (no pick to build) | N/A |

## 11. List view and event editor

| element | spec value | build value | status |
|---|---|---|---|
| The list view | full CRUD on all the user's data: a timeline list view reached by a simple button in the visual, styled like the sessions view with search, FULL SC… | Full screen with a back button, a search pill and sticky cluster dividers; the list takes the title row over rather than stacking a second bar under it (index.html:39-56; menu.ts; main.ts:254-259) | MET @8aec885 |
| Placement | the full timeline and event editor live behind a menu, off the main journey, with a one-line banner saying editing by chat also works | Behind the menu button, off the chat journey (index.html:17,39) | MET |
| Open-list button | 44x44px, border 1px `--line`, border-radius 8px, background `--panel`; glyph three lines, viewBox `0 0 16 12`, `stroke-width="1.8"`, round caps | `.iconbtn.listbtn`, 44x44, 1px `--line` border, radius 8, `--panel` background; glyph viewBox `0 0 16 12`, `stroke-width="1.8"`, round caps (index.html:17-19; theme.css `.listbtn`) | MET @8aec885 |
| Back button | 44x44px, no border, colour `--data`; chevron path, viewBox `0 0 22 22`, `stroke-width="2"`, round caps and joins | `.backbtn`, 44x44, no border, colour `--data`, `margin-left:-10px`; chevron `M13.5 4.5 7 11l6.5 6.5`, viewBox `0 0 22 22`, `stroke-width="2"`, round caps and joins (index.html:41-43; theme.css `.backbtn`) | MET @8aec885 |
| Sheet container | absolute, left/right/bottom 0, flex column, border-top 1px `--line`, top offset computed from the title row's bottom | `#menu-screen` is a flex-column screen holding its own 44px bar, the search, the scrolling body and the footer, and the chat title row is hidden while it is up, so it renders the geometry the absolute sheet does. The picture's prior state survives because the chat screen is only hidden, never rebuilt (index.html:39-56; main.ts:254-259) | MET @8aec885, ASSUMED equivalent to the mockup's absolute sheet |
| Search bar | height 44px, `17px "Libre Franklin"`, border-radius 22px pill, border 1px `--line`; placeholder "Search events" | `.search input`, height 44, `400 17px var(--sans)`, radius 22 pill, 1px `--line`, placeholder "Search events"; filters on label, person and target names, every word must hit; clears on back (index.html:47-49; menu.ts; theme.css `.search`) | MET @8aec885 |
| Cluster divider | sticky top, height 40px, `600 15px "Libre Franklin"`, showing the chapter label and "N moments", or "unplaced" ("No date yet" as built) | `.div` sticky top, height 40, `600 15px/1.2 var(--sans)`, chapter label left and "N moments" right in `400 13px` mono `--faint`; events in no chapter fall under "unplaced" (menu.ts; theme.css `.div`) | MET @8aec885 |
| Cluster divider count wording | the mockup writes `eps[ci].length+' moments'`, so a one-event chapter reads "1 moments" (timeline-converged.html `.tl-div`) | "1 moment" for a single-event chapter, "N moments" otherwise (menu.ts). Reason: UI_SPEC states the value as "N moments" and rules nothing on the singular, so the mockup's plural is a defect rather than a chosen value; changed deliberately and the two menu-list goldens were re-taken with it | NEEDS-OWNER |
| List row | min-height 56px, padding `8px 16px`, border-bottom 1px `--line`; line 1 `400 17px/1.3 "Libre Franklin"`; line 2 `400 13px/1.3 "IBM Plex Mono"` colo… | `.row{min-height:56px;padding:8px 16px;border-bottom:1px solid var(--line)}`; `.r1{font:400 17px/1.3 var(--sans)}`, `.r2{font:400 13px/1.3 var(--mono);color:var(--faint)}`; both lines ellipsise, column flex with a 3px gap (theme.css `.row`) | MET @8aec885 |
| Row summary coding | must not overflow the phone; use abbreviated codes, e.g. `S↑ A↑ F= R conflict→mom` | The meta line is `Mon YYYY · person · S↑ A↑ F= R conflict→Mom`, with `△names` appended for triangles; the chapter label moved to the divider (menu.ts) | MET @8aec885 |
| Row tap state | `.tl-row.on, .tl-row:active { background: var(--tint) }` | `.row.on, .row:active { background: var(--tint) }` (theme.css `.row`) | MET @8aec885 |
| Inline editor | padding `12px 16px 16px`, background `--bg` | `openEditor` is inserted directly after the tapped row, `padding:12px 16px 16px`, background `--bg` (menu.ts:49-53; theme.css:466-473) | MET |
| Editor scope | everything `schema.Event` carries, as the Pro app's EventForm does; the layout may be simplified | Sections What, Who, Words, When and Shifts, with kind, person, spouse, child, summary, details, where, when, ended, certainty, the three shifts, Δ relationship, targets and triangles (editor.ts:135-195) | MET |
| Event kinds | shift, birth, adopted, bonded, married, separated, divorced, moved, death | `EventKind` values rendered as the What chips (editor.ts:136) | MET |
| Relationship kinds | fusion, conflict, distance, overfunctioning, underfunctioning, projection, defined-self, toward, away, inside, outside, cutoff | `Relationship` values plus a "none" option (editor.ts:174-177) | MET |
| Certainty values | unknown, approximate, certain | `Certainty` values, defaulting to certain (editor.ts:152-157) | MET |
| Field labels | "Summary", "Details", "Where", "When", "Ended (optional)", "Certainty" | "Summary", "Details", "Where", "When", "Ended (optional)", "Certainty" (editor.ts:146-152) | MET |
| S, A, F fields | segmented up / down / same / none | Each shift renders as chips of up, down, same and none (editor.ts:160-172) | MET |
| Δ relationship placement | at the SAME level as Δ symptom, Δ anxiety and Δ functioning: a field label under one "Shifts" heading, never its own section | A `.lab` reading "Δ relationship" under the single `.sec` heading "Shifts", alongside the three variables (editor.ts:158-177) | MET |
| Relationship field shape | not a single value: a kind AND the people involved, mover to targets. The editor must break it out into its people permutations | A kind chip group plus a multi-select targets group, and a triangles group (editor.ts:174-192) | MET |
| Relationship sub-field visibility | follows `EventForm.qml` exactly: the three shifts and Δ relationship show only for kind=shift; the targets picker appears only once a relationship… | The shift block shows only for kind=shift; the targets block only once a relationship kind is chosen; the triangles block only for inside and outside. Target labels match the ruling exactly, including "Inside(s) 1" for outside and the "Person 2" fallback; triangle labels are "Outside(s)" for inside and "Inside(s) 2" for outside (editor.ts:55-80,158-192,217-228) | MET |
| Editor segmented chips | height 32px, min-width 44px, `500 13px "IBM Plex Mono"`, border-radius 6px; selected: border and colour `--data`, background `--tint` | `.seg{height:32px;min-width:44px;font:500 13px var(--mono);border-radius:6px}`, `.seg.on` `--data` on `--tint`; padding and row gap now match the mockup's `0 10px` and `12px 8px` (theme.css `.seg`) | MET @8aec885 |
| Save button | full width, height 44px, background `--data`, colour `#fff`, border-radius 8px | `.acts .save` height 44, `--data` background, `--onaccent` text, radius 8 (theme.css:511-520) | MET |
| Delete button | min-width 92px, height 44px, border 1px `--ask`, colour `--ask` | `.acts .del` min-width 92, height 44, 1px `--ask` border, `--ask` text, rendered only when editing an existing event (editor.ts:193-194; theme.css:521-530) | MET |
| Add-event button | full width, height 44px, border `1.5px solid var(--move)`, colour `--move`, border-radius 22px pill, in a footer | `.addbtn` reading "+ Add event", full width, height 44, `1.5px solid var(--move)`, colour `--move`, radius 22 pill, in a `.foot` under the list (index.html:52-54; theme.css `.foot`, `.addbtn`) | MET @8aec885 |
| Menu banner copy | "You can also edit just by chatting." | "You can also edit just by chatting." as `.banner` (menu.ts:8,39; theme.css:445-451) | MET |
| Diagram / family switcher row | name `13.5px Libre Franklin`; sub `13px mono` = "N sessions · <when>"; `✓` in `--data` on the current one; current-row 3px `--data` left bar in the… | No diagram switcher in web/src, and none is buildable yet: the page is bootstrapped with a single `diagram_id` from `user.free_diagram`, and no endpoint lists a user's diagrams or their session counts (routes.py:36-40) | MISSING — blocked on a backend list endpoint |
| Chapter Shelf | sticky name rail 92px under a 560px viewport else 132px; chapter cards `rx:12` fill `--card` stroke `--hair`, width `clamp(30, 34*sqrt(sceneCount)*… | not applicable (no pick to build) | N/A |
| Quiet Threads | sticky name rail 84px under 560px else 118px; lane gap `clamp(30, floor((H-rulerH-60)/laneCount), 54)`; three altitude modes by pixels-per-year; si… | not applicable (no pick to build) | N/A |

## 12. Type and colour tokens

| element | spec value | build value | status |
|---|---|---|---|
| Type scale, binding | screen title 17/600; body 17/400; secondary 15/400; caption 13/400-500, uppercase section headers at +0.4 tracking; absolute FLOOR 13px, mono inclu… | Title and body both at 17px (theme.css:55,86,271,462,484), mono utility text at 13px (theme.css:107,129,143,185,308,319,463,475,506). Nothing below 13px in theme.css. `.btn` at `500 15px` with `min-height:36px` is the one control under the 44 floor (theme.css:429-441) | PARTIAL |
| Mono face | IBM Plex Mono, a utility face for data, chips, dates and labels, at 13 or 15, never below 13 | `--mono: "IBM Plex Mono"` on data, chips, captions and labels (theme.css:17) | MET |
| Body face | Libre Franklin, weights 400/600/800, `system-ui, sans-serif` fallback, 15px/1.5 base | `--sans: "IBM Plex Sans"` (theme.css:16; index.html:11). Libre Franklin is not loaded | CHANGED |
| Type scale as actually built | title 15px, row body 13.5px, bubbles 16px, mono utility text pinned at 13px throughout | The build is at or above the floors the mockups missed | MET |
| Light palette, canonical | `--bg #f7f6f2; --ink #26312f; --faint #9aa5a1; --line #d8d5cc; --data #0e7d78; --ask #c98a1b; --move #2e9e57; --panel #fff; --shadow rgba(38,49,47,… | `--bg #f7f6f2`, `--panel #fff`, `--ink #26312f`, `--line #d8d5cc`, `--data #0e7d78` all match; `--ask #a8720f`, `--move #217a44`, `--faint #6e7a77` do not (theme.css:4-11) | CHANGED |
| Dark palette, canonical | `--bg #171d1c; --ink #e6e9e6; --faint #6d7a76; --line #31403c; --data #3fc4bc; --ask #e0a83f; --move #5fce85; --panel #1f2725; --shadow rgba(0,0,0,… | `--bg #171d1c`, `--panel #1f2725`, `--ink #e6e9e6`, `--line #31403c`, `--data #3fc4bc`, `--ask #e0a83f`, `--move #5fce85` all match; `--faint #93a09c` against `#6d7a76` does not (theme.css:22-32) | PARTIAL |
| Token semantics | teal `--data` = the record; amber `--ask` = the record asking; one green `--move` = every move and action | Teal is data, amber is asking, one green is the move vocabulary, stated in the file's own header (theme.css:1-2,181) | MET |
| Theme switching | tokens redefined under `@media (prefers-color-scheme: dark)` guarded `:root:not([data-theme="light"])`, and again under `:root[data-theme="dark"]`… | `@media (prefers-color-scheme: dark)` guarded `:root:not([data-theme="light"])`, repeated under `:root[data-theme="dark"]` (theme.css:20-47) | MET |
| Themeability | the design must be easily restyled so colour schemes can be A/B tested; no single scheme is assumed | Every component colour is a token; the only literal hexes are in the two `:root` blocks (theme.css:3-47) | MET |
| Palette as built, FD-362 | `--ask #a8720f` light, `--move #217a44` light, `--faint #6e7a77` light; new token `--ask-tint` `rgba(168,114,15,.1)` light and `rgba(224,168,63,.14… | `--ask-tint` and `--onaccent` present as described (theme.css:13-14,31-32) | MET |
| Move-language file tokens | `--data` and `--self` both `#2e9e57` light / `#5fce85` dark, i.e. the single action green; `--ask #c98a1b` / `#e0a83f` | The build keeps `--data` teal and `--move` green as separate tokens (theme.css:9-11) | CHANGED |
| Two-token scheme in older files | `--data` teal for chalkboard chrome, `--move` green for the glyphs | The build follows the two-token split | CHANGED |
| Second design system | serif and mono editorial: Newsreader + Public Sans + IBM Plex Mono; `--ink #242A2E`, `--paper #F2F3F0`, `--card #FBFBF9`, `--muted #68716F`, `--hai… | Not used | MET |
| Play-by-play system | `--page #eaeeec; --card #fff; --card2 #f3f6f4; --ink #111f1c; --mute #5c6f6b; --rule #d2dbd7; --teal #0a8b80; --teal-ink #046a61; --teal-soft #d8ec… | Not used | MET |
| Verdict colours | `--ok #3a7d44` / `--bad #a4482e` light; `#6fbf7a` / `#e0785c` dark | not applicable (no pick to build) | N/A |
| SVG text default | every `<text>` inside the phone forced to `font-family:"IBM Plex Mono"; fill:var(--ink)` | No blanket rule; each SVG text class sets its own family, `.ini` sans and `.nm` mono (theme.css:184-185) | CHANGED |
| Type floor enforcement | `legibility.py`: Playwright at viewport 1320x1000, device scale 2. Fails on any two visible text runs overlapping by more than 1.5px in both axes,… | No legibility gate script in the worktree; `web/tests/visual/moves.spec.ts` covers the gestures as visual goldens | PARTIAL |
| Font size defect | the incorporated design was rejected outright on type size ("I can't read anything in the visual. everything is tiny"), and font size was confirmed… | Nothing in theme.css renders below 13px | MET |

## 13. Animation and timing

| element | spec value | build value | status |
|---|---|---|---|
| Move story loop | every move animation runs the same length: 8 seconds, or an 8s multiple (10s, 12s) for the heavier storm and field marks | The only move animations are `draw 0.6s forwards`, `drain 1.4s infinite` and `tremble 1.2s infinite` (theme.css:207,225,234). Nothing runs an 8s story loop | MISSING |
| No mid-animation pivot | the emotional field must not change frequency or behaviour when the cutoff lands; it stays and is obstructed | The field does not pivot because it never animates: two static circles (moves.ts:75-79; theme.css:200) | PARTIAL |
| Defined-self delay | a delay between the actor turning green and the other person settling, so cause and effect reads | Green from the first frame, no storm, so there is no delay to read (moves.ts:279-285) | MISSING |
| Feel | the play-by-play must feel right: no timing gaps, no symbol gaps, no styling errors | — | UNCHECKED |
| Immediate start | a control that starts something starts it immediately, not on the next tick of a shared clock | The Play button calls `playThrough` on the tap (main.ts:194-199) | MET |
| Screen transform / filter | `.24s ease` | No transition on `.screen` (theme.css:75) | MISSING |
| View height change | `.25s ease` (.24s as built in chat-first-app) | No height transition; the height is written inline per render (picture.ts:377) | MISSING |
| Chapter zoom | `.6s cubic-bezier(.4,0,.2,1)` on transform plus `.6s` on opacity, opacity to 0.25, resolving at 620ms; instant under reduced motion or fast mode | No zoom transition in picture.ts | MISSING |
| Chat opacity swap | `.15s` | No opacity transition on `.chat` (theme.css:256-265) | MISSING |
| Chapter-box pulse | opacity `.35 → 1 → .35`, `2.2s ease-in-out infinite` | No `pulse` keyframe in theme.css | MISSING |
| Trace fade | `tracefade 2.2s ease-out forwards`, holding solid through 40% (2400ms as built in chat-first-app) | No `tracefade` keyframe in theme.css | MISSING |
| Question-mark pulse | opacity `.55 ↔ 1`, `2.8s ease-in-out infinite` | No `ask` keyframe; `.qm` is static (theme.css:178-179) | MISSING |
| Settings pane push / pop | `.22s ease` translateX; teardown at 220ms | No settings stack | MISSING |
| Sessions sheet rise | 260ms, `cubic-bezier(.4,0,.7,.5)` opening and `cubic-bezier(.3,1.25,.5,1)` settling; wire crossfade on a family switch 300ms | No sheet | MISSING |
| Micro-symbol keyframes | `gbuzz .3s` (±2px), `gflow` stroke-dashoffset to -32 tied to its parent's duration, `gshake 1.1s` (±2-2.5px), `gsparkp .5s` (scale .75↔1.1, opacity… | Replaced by `draw`, `drain`, `tremble`, `blink` and `bounce` (theme.css:207,225,228,233-240,296,334) | CHANGED |
| Move-language keyframes | `buzz .28s`; `sparkp .5s` (scale .7↔1.15); `tarrow 8s` (opacity 0 to 8%, 1 from 12-50%, 0 from 60%); `flow 1s` (dashoffset -40) or `.45s` for proje… | None of the ratified keyframes exist; three generic ones stand in (theme.css:228,233-240) | CHANGED |
| Slide gesture | SVG `animateTransform` translate, `dur="1.2s" fill="freeze"` | No `animateTransform`; a static transform attribute instead (moves.ts:62-64) | CHANGED |
| Toast | opacity transition .2s, auto-dismiss at 1500ms (2200ms as built), fade-out 220ms | No toast in index.html or theme.css | MISSING |
| Long-press threshold | 500ms for a session row; 450ms for a card title; 400ms for a crumb or a list row | No long-press handler in web/src | MISSING |
| Reduced motion | all transitions inside the picture forced to 0s, `.pulse` disabled entirely; in the artifact family all animation and transition durations forced t… | `@media (prefers-reduced-motion: reduce){.ss *{animation:none!important;transition:none!important}}` (theme.css:241-243). Scoped to the picture, so the chat's blink and bounce keep running | PARTIAL |
| Finger cursor (gallery only) | 22x22px circle, `margin:-11px 0 0 -11px`, background `--finger`, border `2px var(--fingerring)`; move `left .22s ease, top .22s ease`, opacity `.15… | not applicable (no pick to build) | N/A |
| Shared 12s demo loop | one fixed cycle, same beats on every phone: 0-1 idle, 1-3 open, 3-5 pick, 5-7 re-enter, 7-10 edit, 10-12 close and save | not applicable (no pick to build) | N/A |
| Loop control defect | clicking "loop" on a gallery example does not start the animation | not applicable (no pick to build) | N/A |
| Keyframes as built, FD-362 | `draw .6s ease-out forwards` dashoffset 240 to 0; `drain 1.4s linear infinite` dashoffset -24; `tremble 1.2s linear infinite` five-step ±2px holdin… | `draw`, `drain`, `tremble`, `blink`, `bounce` all present as described (theme.css:207,225,228,233-240,296,334) | MET |

## 14. Tap and scroll behaviour

| element | spec value | build value | status |
|---|---|---|---|
| Tap target floor | 44x44px minimum on every interactive element, 48 preferred for primary actions; the visual may be smaller (a 24px glyph inside a 44x44 button); 8px… | `.iconbtn`, `.send`, `.field`, `.editor .f`, `.acts .save`, `.acts .del` and every `.ss-hit` are 44 or more; `.seg` is 32 high with a 44 min-width; `.btn` is `min-height:36px`, so Play and Done are under the floor (theme.css:87-98,162-175,391-416,429-441,476-530) | PARTIAL |
| Spacing | side gutters 16px; related items 8px; groups 16-24px; section breaks 32px; content never closer than 16px to the phone edge | Side gutters are 16px on the pin label, caption, rows, banner and editor; the chat pads 12px and the input bar 10px (theme.css:106,251,263,388,456,467) | PARTIAL |
| Scrolling | every scroll area supports wheel, trackpad, touch drag AND mouse drag; a drag handler is required; `touch-action: pan-y`; `overscroll-behavior: con… | `.chat` and `.scroller` are plain `overflow-y:auto` (theme.css:256-259,444). No `touch-action`, no `overscroll-behavior`, no drag handler in web/src | MISSING |
| Momentum | wheel scrolling in addition to click-and-drag, with momentum, so the surface feels native on iOS and macOS | No drag or momentum handler in web/src | MISSING |
| Outer-page scroll defect | a demo's scroll target applied to the outer page made the gallery scroll itself after a while | `body{overflow:hidden}` and `.app{height:100dvh;overflow:hidden}`, so the outer page cannot scroll (theme.css:51-57,63-71) | MET |
| The coach keeps the chalk | every tap loops into chat; the coach never hands over the chalk. A drawing is conjured by the coach, never by the user driving the picture | The picture draws only from a coach turn or Play; a tap records a Look and changes only the selection (main.ts:202-213; caption.ts:198-212) | MET |
| Look then say | the first tap looks and is free, showing a title or a caption; the second tap is a chip and speaks | `reduce()` returns a Look with no insert on the first tap, and a Say with an insert on the chip tap (caption.ts:198-226) | MET |
| Every tap is learning data | including looks that send nothing; visible to the coach as context, and first on the A/B test list | Each outcome carries a `record` of kind Look, Say or Play against the item touched (caption.ts:169-240) | MET |
| Picture simplicity | the picture stays exceedingly simple; one tap to reveal a title is acceptable; crowding means doing too much | One wire, at most three word rows, one caption row (picture.ts:427-456; main.ts:173-191) | MET |
| Label band tap | one 44px band spanning all three label rows at top 45px, width x1-x0. The row nearest the tap wins, by `abs(ROWS[row] + 7.5 - y)` | One `.ss-hit` band at `ROWS[0]+1`, height 44, full width; `rowAt` picks the nearest row by `|ROWS[row]+7.5 - y|` (picture.ts:135-147,368-370) | MET |
| Moment tap zones | buttons of width `(x1-x0)/nz` where `nz = max(1, floor((x1-x0)/44))`, so zones are always at least 44px wide, at top 89px, height 44px | `zones()` splits the wire into `floor((x1-x0)/44)` zones, each at least 44 wide, centred on the wire; `cycle()` advances then returns to nothing (spotlight.ts:125-148; picture.ts:371-378) | MET |
| Hit press and focus states | `:active { background: var(--tint) }`; `:focus-visible { outline: 2px solid var(--data); outline-offset: -2px }` | `.ss-hit:active{background:var(--tint)}` and `:focus-visible{outline:2px solid var(--data);outline-offset:-2px}` (theme.css:174-175) | MET |
| Second tap on a selected moment | jumps to the source: scrolls the chat to the bubble where the moment was coded and highlights it with `.traced` for 2.2s | The second tap is the caption's ask chip, which speaks into the composer; it does not jump to the message that coded the moment (main.ts:184-191; caption.ts:213-226) | CHANGED |
| A new coach turn | clears the current selection and re-lights the newly named set | `spotlight()` clears the selection and re-lights the named set (picture.ts:112-119) | MET |
| Tap a datum to see where it was mentioned | as demonstrated in the `base` frame | No jump-to-source path in web/src | MISSING |
| Episode hover | `filter: brightness(1.2)` | not applicable (no pick to build) | N/A |
| Caption actions as built | "[Ask about this]", "[Ask when]" on the shelf, plus a "Play" button when the selection maps to a stretch | "Ask about this", or "Ask when" on the shelf, plus a Play button when the selection maps to a stretch (main.ts:184-191) | MET |
| Tap a chat bubble | traces to the picture mark it refers to, with a 2.2s highlight fade | Only chip buttons inside a bubble are tappable (chat.ts:29-52) | MISSING |
| Tap an amber question mark | opens the question inline, or aims the picture at the relevant lane | not applicable (no pick to build) | N/A |
| Oversized hit areas | glyphs wrapped in a transparent hit shape drawn well beyond the visible mark | `.chip::before{inset:-9px -4px}` grows a chip's target beyond its box (theme.css:356-360) | MET |

## 15. Other

| element | spec value | build value | status |
|---|---|---|---|
| Push notifications | default to few, then experiment upward; proactive messaging defaults to near zero, firing only when a dated fact lines up with a real anniversary | No proactive or notification code in web/src | MET |
| "While it's calm" prompting | valuable, an A/B test candidate | — | UNCHECKED |
| Design-round method | mockups with one-line captions, wide divergence first, converge later; land ONE concept per area; no polish before a pick; idea rounds on cheaper m… | not applicable (no pick to build) | N/A |
| How options are described | common words, explicit and specific; no coined vocabulary, no clever framing, no egocentric captions | not applicable (no pick to build) | N/A |
| Symbols in context | symbols must be shown inside the real design, not as standalone concepts; pixel-perfect interactive mockups come before code | not applicable (no pick to build) | N/A |
| Visuals not tables | design decisions must be communicated as visuals, never as tables | not applicable (no pick to build) | N/A |
| Platform | the rebuild is web-first: simple, light, elegant, easy dev flow, easy release and distribution, no Qt tie | A Vite web app, no Qt (web/package.json, vite.config.ts) | MET |
| Manual editing alongside chat | stays, with full bidirectional reactivity; chat tool calls control everything in the app | The timeline list and editor sit behind the menu alongside the chat (menu.ts; editor.ts) | MET |
| Friction reports | the app self-files them; chat can explain app usage from the reference manual | — | UNCHECKED |
| Clusters | model-derived and stored; the model may group and name, never invent members | Chapters arrive with the timeline and are read, never invented, by the page (types.ts `Chapter`; picture.ts:229-231) | MET |
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
