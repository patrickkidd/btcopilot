# Small-screen data views from shipped apps, and what they could carry here (2026-09-23)

Twenty-four views from real phone apps that get one idea across in a small space, then a
mapping of each of the eight things the picture must say onto the devices that could carry
it in 390 by 132 pixels. The rulings in PICTURE_IDEAS.md bind: event dots at one height
[R-0377], nothing draws what changed [R-0372], question marks off [R-0359], three
dimensions or motion only when flat cannot do it, and a concept must carry a real message
on Patrick's own record or it stays an idea [R-0380].

## The views

**Garmin Connect — sleep stages.** The night as one horizontal bar cut into colored bands,
each band a stage. Device: stacked band at true width. Reads instantly because width is
time and nothing has to be counted.
[garmin.com](https://www.garmin.com/en-US/blog/health/garmin-sleep-score-and-sleep-insights/),
[wareable](https://www.wareable.com/garmin/garmin-sleep-tracking-guide-7529)

**Garmin Connect — Body Battery.** One number from 5 to 100 with a filled curve running
under it across the day. Device: annotated single number over a filled curve. The number
answers first; the curve only says how it got there.
[garmin manual](https://www8.garmin.com/manuals/webhelp/GUID-5D183A14-BB43-4A9B-B441-5F824214CE40/EN-US/GUID-87E1392B-2C55-40B7-A1FF-3AB9252DA0A0.html)

**Apple Fitness — activity rings.** Three nested rings closing toward a goal. Device: ring.
Fullness is read without a scale, and Apple forbids restyling them so the shape means one
thing everywhere.
[Apple HIG](https://developer.apple.com/design/human-interface-guidelines/activity-rings)

**Apple Health — trends.** An arrow and a short line of words saying a measure has moved
and for how long. Device: single sentence with a number. No chart at all, so there is
nothing to decode.
[Apple support](https://support.apple.com/en-ca/guide/iphone/iphe3d379c32/ios)

**Apple Watch — Vitals, typical range.** Last night's readings against the range built from
the last seven nights, with anything outside it colored differently. Device: band of normal
with the odd one marked. It says "this is unlike you" without naming a threshold.
[Apple support](https://support.apple.com/en-us/120142)

**Apple Health — sleep.** Stacked bars per night, with week, month and six-month views
behind the same picture. Device: small multiples over one axis.
[Apple support](https://support.apple.com/en-us/108906)

**Apple Health — State of Mind.** Mood logged over time next to what might bear on it.
Device: one curve with other curves offered beside it, never stacked on it.
[Apple newsroom](https://www.apple.com/newsroom/2023/06/apple-provides-powerful-insights-into-new-areas-of-health/)

**Apple Health — average bedtime.** Last night's bedtime shown against the usual bedtime of
the last two weeks. Device: before-and-after split, two marks and nothing else.
[9to5Mac](https://9to5mac.com/2026/02/17/ios-26-4-adds-more-sleep-and-vitals-data-to-apple-health/)

**Oura — score row.** Three numbers across the top of the first screen, everything else
scrolls under them. Device: fixed row of few numbers. The top of the screen never changes
shape, so the eye lands in the same place daily.
[Oura blog](https://ouraring.com/blog/new-oura-app-experience/)

**Oura — day timeline with tags.** The day as a line with the things you marked placed on
it at their time. Device: marks on one line at one height.
[Oura support](https://support.ouraring.com/hc/en-us/articles/360038676993-Using-Tags)

**Oura — Vitals with personal baselines.** Each measure drawn against your own usual range
rather than a population number.
[Oura blog](https://ouraring.com/blog/new-oura-app-experience/)

**Whoop — recovery.** One percentage in very large type in one of three colors, the same
three colors on every screen. Device: annotated single number. Size does the ranking; the
color vocabulary is learned once.
[925 Studios](https://www.925studios.co/blog/whoop-design-breakdown)

**Whoop — behavior insights.** One row per thing you logged, each row saying which way it
moved your recovery, and only after enough entries exist. Device: ranked rows with a
direction. It withholds the row until the data supports it.
[Whoop](https://www.whoop.com/us/en/thelocker/a-new-way-to-see-insights-on-which-behaviors-affect-your-recovery/)

**Strava — fitness.** One slow line with today's marker on it. Device: sparkline with a
marker. Direction is the whole message.
[Strava](https://support.strava.com/en-us/articles/15401765-fitness)

**Strava — fitness and freshness.** Two lines that cross, form read from the gap between
them. Device: two lines and their gap.
[Strava](https://support.strava.com/hc/en-us/articles/216918477-Fitness-Freshness)

**Strava — heatmap.** Every route drawn on top of itself so the paths you take often burn
brighter. Device: accumulated marks on a map.
[Strava](https://support.strava.com/en-us/articles/16046277-a-guide-to-strava-heatmaps)

**Fitbit — sleep.** A drag along the night reads out the stage at that time, statistics
below. Device: one line with a movable readout.
[TechRadar](https://www.techradar.com/health-fitness/fitbits-redesigned-its-sleep-page-to-make-it-more-useful-heres-whats-changing)

**Withings — Vitality Indicator.** Effort, recovery and well-being folded into one mark
with the contributors one tap under it. Device: one mark, reasons on tap.
[App Store](https://apps.apple.com/us/app/withings/id542701020)

**Daylio — Year in Pixels.** One small colored square per day in a calendar grid. Device:
calendar heat grid. Honest about gaps, but it asks the eye to compare how full one part of
the grid looks against another.
[Daylio](https://daylio.net/faq/activity-and-mood-statistics/)

**Bearable — factor effect.** A list of the things you track, ordered by how much each one
goes with better or worse days. Device: ranked rows with a direction.
[Bearable](https://bearable.app/support/howto/the-factor-effect-report/)

**Exist — correlations.** A finding written as one sentence with a number in it. Device:
single sentence with a number. Nothing to read off an axis.
[Exist](https://exist.io/blog/use-cases/)

**Apple Card — spending wheel.** A ring cut into colored slices by category, largest
contributors on tap. Device: ring divided into parts.
[Apple support](https://support.apple.com/en-us/102329)

**Carrot Weather — next precipitation.** A short strip for the coming hour plus a line of
words naming when rain starts. Device: strip plus one sentence. The sentence carries it;
the strip only shows the shape.
[App Store](https://apps.apple.com/us/app/carrot-weather/id961390574)

**Flighty — Live Activity and Dynamic Island.** One line per flight, copied from airport
boards, with a small circular progress mark. Ryan Jones: those boards "have one line per
flight, and that's a good guiding light — they've had 50 years of figuring out what's
important."
[Apple Developer](https://developer.apple.com/news/?id=970ncww4)

**Flighty — Passport.** Every flight you have taken drawn on one map with lifetime totals
beside it. Device: accumulated marks plus a few totals.
[Flighty](https://flighty.com/passport)

**Duolingo — Year in Review, Spotify — Wrapped.** Four or five headline numbers, one per
screen, each with a line of words around it. Device: one number per screen.
[UX Collective](https://newsletter.uxdesign.cc/p/has-duolingos-year-in-review-outshone),
[Failory](https://newsletter.failory.com/p/spotify-s-secret-unwrapped)

**Timehop and Google Photos memories.** One card, this date in an earlier year, nothing
else on screen. Device: one thing, chosen for you.
[Timehop](https://apps.apple.com/us/app/timehop-your-past-photos-memories-every-day/id569077959),
[TechCrunch](https://techcrunch.com/2022/09/14/google-photos-redesigns-its-memories-feature-with-vertical-swiping-more-video-and-other-creative-tools)

**Apple Watch — complications and Live Activities.** Apple's own rule for the smallest
surfaces: show the useful part, not everything, and expect seconds of attention.
[WWDC24](https://developer.apple.com/videos/play/wwdc2024/10098/)

## What could carry each message in 390 by 132

**(a) Where the history gathers into a few clusters.** Garmin's stacked band at true width:
five soft boxes across the picture, each as wide as the years it covers, which is what the
app's line already draws. Showable on Patrick's record now.

**(b) One key shift per cluster.** Apple's trends device — an arrow and a few words above
the box — or Whoop's ranked rows, one row per cluster naming its shift. Needs more data: a
named key shift recorded in each of the five clusters; today only he carries any shift and
only one anxiety shift exists.

**(c) Where the trouble sits and that it moved between people.** Oura's marks-on-one-line
with the marks colored by person, or Bearable's ranked rows with people as the rows. Needs
more data: a symptom recorded in a second person, otherwise every mark sits on him.

**(d) The opening event and what followed months or years later.** Apple's before-and-after
split: the opening event on the left, what followed on the right, nothing between them.
Needs more data: consequences recorded in other people after the two deaths, which the
record does not hold.

**(e) Nearness of dates to a symptom, never proof.** Two dots and a thin joining line with
the distance written above it, the way Carrot writes when rain starts. Showable on
Patrick's record now for the clusters that hold a symptom event; the others show a lone
dot, so it carries on two of five.

**(f) The four variables moving together over time.** Apple's small multiples — four short
sparklines stacked, one per variable, each stepping on its own dates. Needs more data:
functioning and relationship shifts recorded at the dates already on the line.

**(g) Long quiet years as a finding.** The true-width band again: the gaps between the
boxes drawn as long as they really were, with nothing drawn in them. Showable on Patrick's
record now, and it is the one message his record states loudly.

**(h) The family as one unit across generations.** Flighty's Passport device — everyone
drawn once on one small picture with the trouble lit — or shelves, one per generation.
Needs more data: the traditional family diagram and its auto-arrangement, which are not
built [R-0379], plus recorded shifts in the older generations.

## Candidate hybrids

1. The line already in the app with one line of words above it, written the way a weather
   app says when the rain starts, naming the nearest thing worth saying today.
2. The line with true-width cluster boxes, and inside any box that holds a symptom event,
   two dots joined by a thin line with the distance in words above it.
3. The line at rest; a tap on a cluster swaps the picture for a before-and-after split of
   that cluster's opening event and what followed.
4. A fixed row of three or four plain words across the top naming the newest cluster, the
   way Oura fixes its score row, with the line drawn underneath.
5. Four short stacked sparklines, one per variable, over a row of event dots at one height
   — worth building only once functioning and relationship shifts exist.

## What happened to the hybrids (2026-09-23)

Three of the five were drawn on the app's own line as round 8 and judged as a stranger would
read them, at phone width in both themes, with every tap driven:
https://claude.ai/artifact/WrGWM6m2cXJfQ3FLHnNMu3

- **1, one line of words above the line — kept, and to be built first.** It is the app's line
  untouched with one row of words over it, the only one a stranger can act on without reading an
  explanation, and the only one unchanged at 120 events. Two faults to fix first: at rest the
  line parks on 2002 to 2024 while the sentence names 1994 and 1996, so words and picture talk
  about different stretches; and the sentence is written in the row that names the view, so the
  first tap replaces it with a cluster title.
- **2, the gap drawn inside a cluster box — killed.** Inside a box the app spreads the dots
  evenly rather than at their dates, so two brackets both reading "about a year" came out 9 and
  13 pixels long: the picture contradicts its own words.
- **3, before and after on a tap — killed as drawn, the idea kept.** The app's cluster tap
  already opens the whole cluster; replacing that with two moments in words is a narrower view
  than the one it costs. It belongs as a mark inside the cluster view that already exists.

Not drawn: hybrid 4 (a fixed row of words naming the newest cluster) and hybrid 5 (four stacked
sparklines, one per variable), the second of which needs functioning and relationship shifts that
the record does not hold.

Three decisions sit on that page and are unanswered: whether the coach's sentence may put two
things side by side when the record holds only their dates; whether one line of words is worth
the picture growing from 132 to 154 pixels and the chat losing 22; and whether the line should
come to rest where the sentence points or always open on today.

