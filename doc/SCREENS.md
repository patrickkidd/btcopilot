# Family Diagram — what every screen does

This is the current truth about every screen in the app and how it behaves, written for the
people who are about to use it rather than for the people building it. Each line is one
behaviour, tagged `[built]` if it is in the app today, `[drawn]` if it is approved on a drawing
but not built, and `[open]` if it is a choice Patrick has not made yet. It is rewritten as
decisions land; the exact sizes and colours live in the internal interface spec, not here.

Updated: 2026-10-02

---

## Landing page

What it is for: the first thing a visitor to familydiagram.com sees; someone already signed in goes straight to the app. [Oracle: R-0601]

- The Alaska Family Systems logo at the top, linking to alaskafamilysystems.com; under it, "Version 3" and the name Family Diagram. In dark mode the logo sits on a light rounded panel so its purple words stay readable. [built]
- The page takes its colours from the logo: purple buttons and links, a thin blue-to-purple band across the top, a faintly cool white ground with dark indigo words in light mode, and a deep indigo ground in dark mode. The logo is also the browser tab's icon. [built]
- One paragraph, in Patrick's words: "An AI coach that keeps the story of your life. Tell it what happened, year by year; the record builds with every conversation, and it gets smarter at seeing patterns in the moments that matter." [built] {R-0602}
- One line says beta access is by direct invitation only. [built]
- "Already invited?": you type your email and tap Send my link. If the address was ever invited, or already has an account, a sign-in link good for one day is emailed to it; the page says the same words whether or not it was. At most five links an hour per address; past that nothing is sent and the page still says the same words. [built]
- "Not invited yet?": your name, your email and, if you like, a few words about you and your interest (up to 2,000 characters), then Ask to join. A name or email split over two lines, or an email without exactly one @ or with a space in it, is refused in plain words. The request is emailed to Patrick with your address as the one to reply to; nothing is kept in the database. [built]
- Both forms carry Cloudflare's Turnstile check that you are a person, because both send email; a failed check sends nothing and asks you to try again. [built]
- The settings are two keys from a Turnstile widget made in the Cloudflare dashboard, `FLASK_TURNSTILE_SITE_KEY` and `FLASK_TURNSTILE_SECRET_KEY`, in the box's secrets file. Without them the page still shows but both buttons are greyed out and say the form is not available right now; a development server with neither key uses Cloudflare's test keys, which always pass. [built]
- A tapped button greys out at once, so a second tap cannot send a second email. [built]
- At the bottom: "©", the current year and "Alaska Family Systems", and nothing else. The year is the year of the visit, never typed into the page. [built]

## Signing in

@frame built#f1 | Signed out: the app name, the address you are signing in as, and one button.

What it is for: getting into the app without a password.

- You get an emailed link and tapping it signs you in, so there is no password to make or remember. [built]
- Signing in with an emailed code also creates the account, so there is no separate sign-up step. [built]
- A sign-in lasts about six months, so you rarely sign in twice on the same phone. [built]
- A sign-in is never thrown away early; a session older than the other apps' limit is still read, so you are not signed out in the middle of what you are doing. [built] {R-0337}
- After the first sign-in the app offers to let you use Face ID or a fingerprint instead, and asks only once per phone. [built]
- If you say no to Face ID it waits a month before offering again. [built]
- On a phone the app offers, once, to add itself to your home screen, and shows the exact button to tap. [built]
- If you dismiss the home-screen card it comes back no sooner than a week later. [built]
- The card never blocks the conversation; you can ignore it and keep typing. [built]
- Signed out, you see the app name, who you are signing in as, and one button to sign in. [drawn]
- Invite links sent for review use the machine name rather than a numeric address, so they open on a phone. [built] {R-0234}
- An invite link signs you in as many times as you like until it expires. [built]
- The app is called Family Diagram wherever you can see it. [built] {R-0216}
- The chat app has its own accounts on its own database; old subscribers of the existing Pro app are brought in once rather than shared live with it. [built] {R-0327}

## The chat

@frame built#f2 | A coach reply on a phone naming twelve things it just changed, each one a pill you can tap.
@frame built#f3 | The same reply in a desktop window, where the pills sit several to a row.

What it is for: talking to the coach, which is how everything else in the app gets made.

- You type to the coach the way you would talk to someone trained in Bowen theory, and it answers. [built]
- Dictation on your phone covers talking instead of typing; there is no separate voice mode. [built]
- There are no modes to switch between: coaching, correcting the record, asking how the app works and thinking out loud are all the same conversation. [built] {R-0015}
- The coach adds, changes and removes people, pair-bonds, events and shifts as you talk, and says in the thread what it did. [built] {R-0185}
- Those lines saying what it changed are set apart from the coach's own words, deliberately, and are staying. [built] {R-0186}
- Each line of what it did lights the thing it made in the picture as that line lands. [built] {R-0185}
- Three dots appear in the coach's bubble the moment you send, so the bubble is never blank while it thinks. [built] {R-0184, R-0653}
- The thread stays at the bottom on the newest words while the coach types. [built] {R-0172, R-0231}
- Opening the app again puts you at the bottom of the thread, on the newest words. [built] {R-0231}
- Everything the app says can be selected and copied, including the coach's replies and the lines about what it changed. [built] {R-0183}
- The first time you open it, the coach says it is there whenever you want to think out loud about your family and asks who is on your mind. [built]
- The coach does not message you first unless you ask it to. [built] {R-0017}
- Correcting something in conversation changes the record in place, and older references still point at the right thing. [built]
- You can also undo the last thing the coach did by telling it to. [built]
- Before anything else, the coach asks you for your first name, your last name and your birth date, and keeps asking until it has all three. [built] {R-0360}
- Without your birth date the coach has nothing to turn an age into a year, so early events land on years it invented. [built] {R-0360}
- The last sentence of a coach reply is its question and is set in amber. It reads as bold, which is where your eye should go. [built] {R-0358}
- The coach no longer holds out answers for you to tap; you type your own words. [built] {R-0361}
- With a real keyboard, Return sends and Shift-Return or Alt-Return starts a new line; on a touch screen, Return starts a new line and only the send button sends, so a message can have paragraphs. A touch screen is told by its pointer, not by the browser's name. [built] {R-0368}
- The coach's words and the steps it takes arrive as they happen rather than all at the end, so a long turn is never a blank wait. [built] {R-0369}
- The turn runs on the server on its own, so reloading the page, or leaving the app and coming back, picks the turn up where it is. [built] {R-0369}
- Every step the coach takes, reads and changes to the picture included, is a line in its reply, and the lines stay after a reload. [built] {R-0478}
- There is a little room between those lines and the coach's words. [built]
- If a reply fails, the lines that landed stay and [try again] carries on the same turn without sending your words again. [built] {R-0477}
- Each line names the event or person it touched by the same label used everywhere else. [built]
- Speak replies reads the coach's replies out loud, on an iPhone too. [built]
- In each of those lines, the name of the thing it touched is in italics, set apart from the verb, as in "Changed *Dad's move*: date 1990". [built] {R-0528}
- Under each coach reply that has words there is a thin, line-drawn play button, as in the Claude Code mobile app; tap it to hear that reply, tap again to stop. [built] {R-0521}
- On an iPhone, a long message in the message box scrolls without its lines drawing over each other. [built]
- A notice from the app, or a coding task waiting for you, shows as a small card above the message box. Folded, it is two lines and a small mark that it opens: its title on one line and the body on the line under it, each cut short with an ellipsis when it does not fit, with no buttons. A tap on the card shows the whole title and body in place, with bold, italics, links and line breaks, and then, under them, Open with the name of where it goes ("Open Coach settings") when it points somewhere with more to see, and a cross; one pointing at the account view, its Notices or nowhere has only the cross, so it is read before it is acted on; a tap on the words folds it again, and unfolding does not count it read. It is never in the thread and never covers the page. [built] {R-0611}
- One shows at a time, the newest. It stays there until you tap Open, which goes to the screen it points to, or the cross, which puts it away; either way it is counted read and does not come back. [built] {R-0611}
- A coach message never shows there, because it is already in the thread. [built] {R-0606, R-0611}
- A tap on a notification lands where it points from wherever the app is: the sessions drawer, the play-by-play drawer, the new-event form, the account view and any other screen are put away, then the thread scrolls to its message and lights it; a task or notice instead opens the account view at its root and the page it names. [built] {R-0055}
- A coach message written while the app was open elsewhere, or away, appears in the thread when you come back to the app, when you tap its notification, and within a minute while the app is in front; the thread is only drawn again when something new is in it. [built] {R-0606}
- Admins and auditors see a small circled (i) at the top right of a coach reply; tapping it opens the coach's own notes for that turn in a panel that grows out of the bubble and shrinks back into it. Nobody else sees the notes. [built] {R-0520, R-0522, R-0529}
- While the coach replies the message box stays open and the Send button is a Stop button. A message you send meanwhile waits under the line "Sends when the coach finishes" and goes the moment the reply ends. [built] {R-0674}
- Stop ends the coach's turn at its next step. Anything that turn had added to or changed in the record is taken back, the picture and the lists show it gone, and a grey line "Stopped" stays under your words, after a reload too. [built] {R-0674}
- Reloading the page never changes what you see: an open vote, a mode that is on and a selection all come back as they were. [built] {R-0652}
- With Conversation Feedback on, a strip under the header says it is on, that replies will be slower, and to vote; a tap on the strip turns it off. [built] {R-0673}
- With it on, each coach reply arrives beside one other reply to the same words, neither one named. You mark every reply that is acceptable and the one that is best, may add a note of at most two sentences, and tap Vote. [built] {R-0636, R-0639, R-0645}
- The message box is locked until you vote. [built] {R-0638}
- After the vote the coach's real reply is labelled Coach and the other is folded under it; which model wrote the other is never shown. [built] {R-0636, R-0644}
- Replies made with Conversation Feedback on are amber, in light and dark mode, and stay amber after a reload with their fold and how each was voted. [built] {R-0673}
- The circled (i) for the coach's notes is hidden while a vote is open. [built] {R-0646}

## The picture at rest

@frame built#f5 | One event on the line: a single dot, no box around it.
@frame built#f6 | A dense record: events that belong together are boxes on the line, each showing how many it holds.
@frame built#f4 | A brand new record: nothing is on the line yet.

What it is for: the one picture, always above the chat, that is the app's memory of your family.

- One picture sits pinned above the chat and never appears and disappears. [built] {R-0002}
- It keeps a fixed height whatever it is showing, so the chat below it never jumps. [built] {R-0210}
- At rest it shows your clusters over time on one line: a horizontal line with marks on it and nothing else. [built]
- The line scrolls sideways a little: the most recent years fill the width and the rest is one swipe away, never more than two screens wide. [built] {R-0381}
- Every event is a dot sitting on the line itself, always at the same height, never sometimes below it. [built] {R-0377}
- An event's words sit far enough above its dot that a thumb can tap one without catching the other. [built]
- An opened group of events prints the real years it covers. [built]
- Only the line and the marks on it are drawn at this size. [built] {R-0005, R-0359}
- The line is drawn a little wider than the screen and slides sideways, so a crowded record still reads at a size you can tap. The most recent years fill the width when it opens; the earlier ones are one swipe to the left, at most two. [built] {R-0381}
- The whole line is never more than two screens wide. A record with far more events on it draws at a coarser scale instead of reaching further, so it is never something you have to work through. [built] {R-0381}
- What stays put while it slides: the height of the picture, the line itself from edge to edge, and the years underneath, which say which stretch you are looking at and change as it moves. [built] {R-0381}
- After a swipe it settles so a cluster is not cut in half at either edge when one is near enough to settle on, and it goes back to the present when the coach answers. [built] {R-0381}
- Marks never move up or down: every event sits on the line at the same height, wherever the line stands. [built] {R-0377}
- The band under the picture reads "tap a cluster" when nothing is picked. [built]
- Tapping a mark once shows its words; nothing is sent to the coach and it costs you nothing. [built] {R-0073}
- Tapping it again sends it to the coach as something you are asking about. [built] {R-0072, R-0073}
- Tapping empty space, or the picture's own name, puts the picture down and clears what was picked. [built]
- A picked event shows its date and its own words in two lines above the line, and the year is written once under the mark. [built] {R-0210, R-0235}
- A picked loose event that is not in any cluster reads exactly like a picked event inside a cluster. [built] {R-0235}
- Tapping the words of the event already picked jumps to where it was coded in the chat. [built] {R-0192}
- The amber question mark is hidden for now, because nobody could tell what it meant. The record still holds its questions and the coach still asks them in words. [built] {R-0359}
- Facts with no date sit on a shelf at the end of the line rather than being placed on it, and the question mark that used to mark that shelf is hidden with the rest. [built] {R-0013, R-0359}
- Tapping a shelf item says the fact out loud and offers to ask the coach when it happened; a shelf item that does nothing is a defect. [built] {R-0047}
- There are no legends anywhere; every mark says itself in a plain sentence when you tap it. [built] {R-0005}
- There is no progress bar and no sense of being finished; what more information would buy is shown as specific questions instead. [built] {R-0007}
- There are no filter buttons and no way to hide parts of the picture by hand. [built] {R-0046}
- The coach aims the picture: its latest message lights the events it names and the rest stay dim. [built]
- At most three events are lit at once, with their words tied to their marks by thin lines. [built]
- A new answer from the coach clears what you had picked and lights the new set. [built]
- When the record is empty the picture says nothing is on your line yet and that it draws itself as you talk. [built]
- A line is only drawn through points when there are at least three of them; below that you see marks, because two points invent a trend. [built] {R-0008}
- A guessed date is drawn as a band rather than a point, so you can see it is a guess and correct it. [built] {R-0009}
- A stretch with no information is dotted, and a stretch you told it did not change is solid, so silence never reads as stability. [built] {R-0010}
- An open-ended state fades after the last time you confirmed it, rather than running to today. [built] {R-0012}
- A death stops everything about that person at that date. [built] {R-0012}
- Order between two guesses is only drawn when the two guessed ranges do not overlap. [built]
- The picture never announces that it is about to change; the invitation is always in the coach's words. [built]
- The warning badge saying the picture might be behind the conversation was removed. [built] {R-0203}
- A nodal event, Bowen theory's term for an event that shifts the family's emotional process, carries a ring on its dot; the coach sets that flag by the clinical definition, never by guesswork. [built] {R-0283}

## A cluster opened

@frame built#f8 | A group of related events opened over the line, with its name, why it is a group, and its events still as marks.

What it is for: one group of related events, opened from the line.

- This section and "The play-by-play" below have not been walked line by line since the strip was redrawn as one pill per cluster and the moves board was rebuilt into a snapshot-based play-by-play on a real family diagram (R-0537 to R-0571). [open]
- Selecting a cluster redraws the same timeline in place with the cluster selected, rather than sliding a second view over the first; a slide is kept only for a real drill-down into something new. [built] {R-0542}
- The grey line above the picture becomes the name of what you are looking at, with a back arrow beside it. [built] {R-0223}
- Tapping either the name or the back arrow goes up one level. [built] {R-0223}
- An open cluster shows its name and the reason it is a cluster, never a list of its events, because a cluster can hold fifteen. [built] {R-0213}
- The events inside stay as marks; tapping one shows its words. [built] {R-0213}
- A cluster needs at least three events to exist. [built] {R-0215}
- Grouping is the coach's judgement, made from what you say as you say it; every grouping carries a one-line reason that says what is in it and what is not; the automatic grouping is only a first draft the coach may overwrite. [drawn] {R-0287}
- A stored cluster carries only its name, its reason, where it came from, and the events in it. [built] {R-0205}
- The coach may group and name events but may never invent an event to put in one. [built] {R-0076}
- The coach decides which events belong together and keeps the groups it already made unless the story gives it a reason to change one, so the picture does not change under you between messages. [built] {R-0371, R-0374}
- Nothing is drawn to show what changed between one reading and the next; if a group changes, the coach mentions it in ordinary conversation. [built] {R-0372}
- The coach never uses a technical word for these groups and never says that an event was added to one; it talks about your family's story. [built] {R-0373}
- A birth, marriage, divorce or death opens a chapter, and the changes recorded around it are what that chapter is about. [built] {R-0375}
- What a group is meant to show you: the one moment the trouble moved, where it sits, who it moved between, what opened it and what followed. That is not built yet. [open] {R-0376}
- A line of words above the picture, the coach naming the nearest thing worth saying today, is drawn and waits on Patrick, because it needs a little more height. [drawn]
- The word for these is clusters, in the app and in the code. [built] {R-0197}
- Backing out of an open cluster always closes it and puts you back on the full line, no matter whether you had picked an event first. [built] {R-0362}
- Clusters are rebuilt from scratch after every turn that touches an event, so the same events can come back under different names; they are meant to stay put and change only when there is a reason. [open]
- Tapping an event's words inside an open cluster does not open an editor; you change an event by chatting about it. [built] {R-0572}

## The play-by-play

@frame built#f9 | The board playing the first move: the people on a ring, the move drawn in green, and one sentence saying who did what.

What it is for: a play-by-play of what people did, one move at a time.
@link https://claude.ai/code/artifact/c523a1c9-b298-49e8-807b-142a8a7470f7 | The ratified move language: every relationship move and variable shift, animated, as the board plays them.

- The board is reached from the picture by the play mark alone, with no words beside it. [built]
- The board grows to fit what it is showing rather than sitting at a fixed height. [built] {R-0173}
- The board now draws a real family diagram, generated by code from your record to the same rules the picture uses elsewhere, one snapshot per date the story needs, rather than a simple ring of people. [built] {R-0546, R-0547}
- One row of controls sits under it, always back, explain and forward, whichever way you arrived. [built] {R-0180}
- The button says "explain", because it makes the coach answer rather than playing an animation. [built] {R-0166}
- Explain is dead only while the coach is still answering the last time you tapped it. [built] {R-0180}
- Each move holds until the sentence about it has finished typing plus about two seconds. [built] {R-0171}
- Every move's own animation runs for eight seconds and is never stretched to match the words. [built] {R-0171}
- The words under the board are a person's name and what they said happened, with no count and no clinical term. [built] {R-0178, R-0162}
- That block keeps room for two lines whether or not it needs them, so the board never changes height. [built] {R-0178}
- The date is written once, under the mark. [built] {R-0178}
- The event being played is drawn last, in the action green, and nothing is drawn behind it. [built] {R-0177}
- The line from the mark up to the words is what tells you which event is being played. [built] {R-0177}
- Moves already played stay on the board, faint and still, so what a move left behind stays visible. [built]
- The grey line above says only the family timeline; the event's own label stays above its mark. [built] {R-0179}
- Tapping a move's chip moves the board and never sends you back to the line. [built] {R-0170}
- You never see the internal names of the symbols; you see what you said. [built] {R-0161}
- The up and down arrows for symptoms and functioning never disappear mid-play. [built] {R-0163}
- The arrow beside a symptom stands exactly as tall as the cross it sits next to. [built] {R-0190}
- Every move mark is drawn in one green, and green means action. [built]
- Amber never marks a move or a symptom, because amber means the record is asking. [built]
- Whether the whole thing reads without a legend, and whether the words and drawings tell the same story, is a judgement only Patrick can make by playing a stretch through. [open]
- Four of the five bugs found playing through a real cluster are fixed: a move aimed at nobody no longer draws on the mover, a bond line no longer shows outside the bond's dates, a second shift on one event now gets its own step, and an event of unknown date keeps its place in the story. [built] {R-0532}
- Still open: telling a separation apart from an ongoing bond, and the captions using app words like "bonded"/"separated", both wait on the theory behind the coach's storytelling being written down in its own session. [open] {R-0532, R-0524, R-0525}

## The row of chips under the picture

@frame built#f7 | An event picked: the row underneath turns into ask about it, have it explained, or find where you said it.
@frame built#f11 | The list of everything in the record, reached from the button at the end of that row.

What it is for: the four things you can do with whatever is picked.

- One row sits under the picture and reads the same whether a cluster is open or an event inside it is picked. [built] {R-0211, R-0212}
- The row is ask, explain, in chat, and the button that opens the lists. [built] {R-0212, R-0221}
- The chips use the chat's own chip style, and ask carries only the word. [built] {R-0212}
- The list button sits at the right-hand end of that row. [built] {R-0221}
- Ask puts the thing you picked into your message so you can type your own words around it. [built] {R-0072}
- In chat jumps to the message where that event was coded. [built] {R-0192}
- In chat only works when the event actually has a message behind it. [built] {R-0220}
- Explain asks the coach to walk you through the cluster, and costs a coach reply. [built] {R-0166}
- The room under the picture is reserved whether or not anything is in it, so nothing below moves when you tap. [built]

## Chips in messages

@frame built#f10 | A thing from your record carried into the box you are typing in, with the coach's question in amber above the answers it is holding out.

What it is for: the coach's references to real things in your record, and yours back to it.

- A chip is a reference to something real: an event, a cluster or a person. [built] {R-0072}
- Chips appear inside the coach's messages and inside your own. [built] {R-0072}
- Tapping one drops that reference into your message and you type your own words around it. [built] {R-0072}
- Sending a reference on its own means "tell me about this". [built] {R-0072}
- Tapping a chip is you speaking, never you steering the coach. [built] {R-0072}
- Tapping a chip for an event in a message picks it in the picture the same way tapping its dot does: the rest fades and its cluster's brackets show. An admin switch per person puts back the old behaviour. [built]
- A chip is the one visual that means "this puts words in the chat", so nothing else ever costs you a turn. [built] {R-0073}
- Chips are one size and show their whole label; they are never cut short and never expand. [built] {R-0169}
- Labels are kept short where they are written: a label over 28 characters is asked for again once, on its own, and the rest of the reply stays as written; one still too long is cut at the last whole word that fits. [built] {R-0169}
- Every chip shows that it has been pressed. [built] {R-0169}
- A reference the coach writes that does not resolve to anything real is dropped rather than left pointing at nothing. [built]
- Messages from earlier sessions carry no chips; references only come back on a live reply. [built]
- The coach never answers with a bare list of chips; a walk-through reads like a person explaining. [built] {R-0160}

## The lists (events and people)

@frame built#f11 | Everything in the record as a plain list on a phone, oldest at the top.
@frame built#f12 | The same list switched to people, with the order it is in at the top.
@frame built#f13 | The events list in a desktop window.

What it is for: seeing and editing everything in the record by hand.

- One button in the row under the picture opens a drawer holding everything in the record. [built] {R-0198}
- The events list and the people list are two tabs in that one drawer, not a filter. [built] {R-0199}
- A third tab, "Questions", holds what the coach is keeping for you: questions under "Food for thought" and "Facts to find", and its impressions under "Impressions". [built]
- You only see questions the coach has actually asked and that are still open; ones you turned down or that led nowhere never show. [built]
- The coach only keeps a fact to find it thinks matters to your family's story, and keeps it when in doubt. [built]
- Tapping a question or an impression puts it in the message box; nothing sends until you do. [built]
- Swipe a question left to dismiss it, and the coach will not ask it again. [built]
- Swipe an impression left for "Doesn't fit", which tells the coach in the chat, or "Partly", which starts a reply for you to finish. [built]
- Each impression shows the things in your record it rests on. [built]
- The list button has no circle round it and sits at the same height as the chips beside it. [built]
- Every label names all the people in it, you included: "Sam & Alex", never "& Alex". [built]
- An event's kind is said once, never "died · died". [built]
- An event that sits in no cluster says why. [built]
- The button sits inside the picture's own frame, matching the sessions button beside the chat input. [built] {R-0198}
- On a phone the drawer slides up over the chat, the picture and the title row, full screen, and its own back arrow is the way out; the chat stays under it while it travels. [built] {R-0345}
- The coding screen's drawer opens the same way from the same button, and still stands beside the thread on a wide window. [built] {R-0345}
- Events are grouped under their cluster, with a heading that stays in view as you scroll so you always know which cluster you are in. [built]
- A cluster of one event reads "1 event", not "1 events". [built]
- Events with no date are grouped under their own heading. [built]
- The lists can be searched. [built]
- Each row shows what happened on one line and the date and people on a second. [built]
- A row's summary uses short codes rather than running off the side of the phone. [built]
- The scrollbar is never covered by a cluster heading. [built] {R-0218}
- Tapping a row opens that event's or that person's detail card as its own page, read-only; its back arrow returns to the list where it was scrolled. [built]
- The line saying you can also edit by chatting was removed from these lists. [built] {R-0219}
- There is a button to add an event; the new event's form slides up over the lists, full screen, with its name and the app's close button at its top. [built]
- An event or a person is changed by chatting about it, from its detail card. [built]
- There is no button for adding a person or an event; you add one by telling the coach. The two forms remain for editing what is already there. [built] {R-0663}
- Every row of the events list shows the word for its kind in the emphasis colour, whatever the kind. [built] {R-0675}

## The event detail view

What it is for: reading one event, and taking it to the chat to comment on it or change it (Patrick's picks D2 to D4, 2026-10-01).

- Tapping a row in the events list opens the event as its own page with a back arrow to the list, read-only: its kind, what happened, when and how sure, who, any shift, where, its cluster, its notes, and the chat message it was said in, which jumps to that message. Nothing on it is a form field. [built]
- A person's name opens that person's card; the cluster opens that cluster on the picture. [built] {R-0201}
- One action sits at its foot, reading "Tap to comment or change this event in chat". It puts the event in the message box as a lit chip and brings up the chat with the box ready to type in; nothing is sent until you send. [built]
- After the message is sent the chip is gone from the box; the coach's reply shows what it changed as any reply does. [built]

## The event editor (parked)

Parked on Patrick's 2026-10-01 decision to try chat-only editing: the form is not reached from the events list or the detail view, no button adds an event (Patrick, 2026-10-02): the address `/app/event/new` still opens the form, and on the coding screen a tapped event row opens it to change or delete that event. Its code is kept so it can come back.

@frame built#f14 | One event opened for correction by hand: its kind, who it happened to, its words, its date and how sure the date is.

What it is for: correcting or adding one event by hand.

- The editor holds everything an event carries: its kind, the people on it, a summary, details, where it happened, when, an optional end, and how sure you are. [built]
- Its fields are big enough to tap comfortably. [built] {R-0174}
- The kinds are shift, birth, adopted, bonded, married, separated, divorced, noted and death. [built] {R-0363}
- A noted event is any other notable event: one person, words that must be there, and a place and a date if you know them. [built] {R-0363}
- A move is a noted event with the place kept; there is no longer a kind of its own for moving. [built] {R-0364}
- A noted event changes nothing about the family, but it is a lead: sitting near a shift it raises the question of what came first, the way a structural event does. [built] {R-0366}
- How sure you are is one of unknown, approximate or certain. [built]
- Every date says how sure it is: an exact day is certain, a month or a year alone is approximate, and "around then" is unknown. [built]
- Symptom, anxiety and functioning are each set to up, down, same or not said. [built]
- A relationship change sits at the same level as those three, under one heading, never in its own section. [built]
- A relationship change is a kind plus the people involved, from the person who moved to the people it was aimed at. [built]
- The list of people a relationship points at is labelled differently by kind, so a conflict asks for the others and an overfunctioning asks who was underfunctioning. [built]
- A third list of people appears only for the inside and outside positions of a triangle. [built]
- The shift fields and the relationship field only appear for a shift; the spouse field only for a bonding, marriage, separation or divorce; the child field only for a birth or adoption. [built]
- Saving drops values that no longer apply to the kind, so changing a shift into a death clears the shift values. [built]
- Saving re-sorts the list by time and redraws the lists and the picture. [built]
- Delete appears only when you are editing something that already exists. [built]

## The person detail card

What it is for: reading one person, and taking them to the chat to comment on them or change them (Patrick, 2026-10-01: the same as for events).

- Tapping a row in the people list opens the person as their own page with a back arrow to the list, read-only: their kind over their name, when they were born and died, their parents, partners and children, the clusters and events they are in, and their notes. Only what the record holds is shown; it keeps no address, contact or living status for a person. [built]
- A name opens that person's card, an event opens that event's card, and a cluster opens that cluster on the picture. [built] {R-0201}
- One action sits at its foot, reading "Tap to comment or change this person in chat". It puts the person in the message box as a lit chip and brings up the chat with the box ready to type in; the chip is gone after the send. [built]

## The person editor (parked)

Parked on Patrick's 2026-10-01 decision to do for people what was done for events: the form is not reached from the people list or any card, no button adds a person (Patrick, 2026-10-02): the address `/app/person/new` still opens the form, and on the coding screen a tapped person row opens it to change or delete that person. Its code is kept so it can come back.

@frame built#f15 | A person opened the same way: a name, a kind, and a line saying births and deaths come from talking to the coach.

What it is for: one person's own details.

- The person's kind field is labelled Kind rather than sex, to keep the category right. [built] {R-0200}
- A person carries buttons to their birth and their death when those exist, jumping to that event's detail view (the person card does this now). [built] {R-0201}
- The jump works in reverse, from an event back to the person. [built] {R-0201}
- Your own birthdate anchors your own line on the picture. [built]
- Every diagram that ever had a chat on it carries a person called Assistant, which is a defect and not yet fixed. [built]
- Under "Born to" the person's two parents are named outright — "Rafael Ortega and Marisol Ortega"; the reader never sees the word bond. [built] {R-0345}
- Somebody with no parents on the record is offered "add parents", a picker asking for a mother and a father, each either somebody already on the record or a name typed there. [built] {R-0345}
- Saving it makes whoever is new, takes the couple those two already are when they are one, and sets this person's parents to it. [built] {R-0345, R-0326}
- Under "Partners" is one row per other person they have ever been a partner of, reading "with Marisol Ortega · married 1970", and a row saying "add a partner". [built] {R-0345}
- A partner row opens that partnership's own small editor: who the other person is and whether they married; when it started and when it ended are events about the two of them. [built] {R-0345, R-0326}
- The people list itself is unchanged: no chips and no second line under a name, because a chip means a tap into the chat. [built] {R-0326}
- A person cannot be their own parent or their own partner, a bond is between two different people, and any two people have one bond ever; the record refuses the rest, so the coach and the scribe are held to it too. [built] {R-0326}
- The record refuses a bond that cannot exist, and names a missing parent rather than guessing who they are. [built] {R-0325}

## The sessions sheet

@frame built#f16 | Your past conversations, newest first, with one button to start a new one.

What it is for: your past conversations.

- A button beside the chat input opens a sheet holding your past sessions. [built]
- The sheet rises from the input bar and can be dragged back down to close. [built]
- Sessions are searchable by their titles, their summaries and the words said in them, with the coach's own search; a session found by its words shows the line that carries them under its title. [built] {R-0347}
- The list is drawn on the notes-list precedent: a small uppercase grey heading per period — today, yesterday, previous 7 days, previous 30 days, then the month — over a rounded group of rows; no clock column, no badges, no pencil. [built] {R-0347}
- Each row is a bold title with the day small at its right (left out under today and yesterday), then two lines of the first thing the client said, so a session can be told apart without opening it. A session nobody titled is named by its first six words, or "New session". [built] {R-0347}
- A "⋯" at the row's right opens the same rename and delete actions as the swipe. [built] {R-0347}
- Rename is green and Delete is red, in the app's own colours for adding and removing. [built]
- The coach titles a session after the first exchange, and you can rename it by hand. [built]
- A session you renamed by hand is not marked; the coach simply never overwrites it. [built] {R-0347}
- Emptying a rename puts the coach's own title back and says so. [built]
- The session you are in is marked. [built]
- Newest activity is first, and the order never changes while you are looking at it. [built]
- A button at the foot starts a new session, and refuses while the current one is still empty. [built]
- With no sessions at all it says past conversations collect here. [built]
- The sheet holds only the sessions of the family the app is on; the family is chosen on the account page, never in the sheet, and a personal user never sees the word case at all. [built] {R-0285, R-0347}
- The buttons at the foot, a professional's upload and new note, are spaced apart. [built] {R-0347}
- The sheet holds no way to coding, the meeting or picking the better reply, and a session row neither opens nor goes on the agenda; those live on the account page, since none of them hangs on the family the app is on. [built] {R-0259, R-0267}
- Someone else's session is simply not found rather than refused, so the app never confirms a session it will not show you. [built]
- The history in the review database is kept across code changes rather than reset. [built] {R-0191}
- Existing diagrams and conversations made before this app must open in it as sessions; old training transcripts are kept out of the list. [built]
- Clearing a record's coding and re-running the coach over the same conversation is a feature still to build. [drawn]
- After such a re-run, chips in the old thread point at events that no longer exist and read as plain words; the re-run is meant to re-link the ones that match. [drawn]

## The account page

@frame built#f17 | Your name and address, the coach and appearance settings, your records and plan, and signing out.

- The button that opens the account page shows its icon. [built] {R-0346}
- Diagrams and Your Plan sit together under a section header "Data"; the Diagrams page is titled "Diagrams". [built] {R-0631}

What it is for: you, your families, your plan, and signing out.

- Your account is reached by the mark at the top right of the title row. [built]
- That mark has no circle drawn around it, because there is no room. [built] {R-0222}
- Tapping it slides the account page smoothly over the app rather than making the app disappear. [built] {R-0225}
- The account page is a list where each row opens its own page with a back arrow, like the phone's own settings. [built]
- The top of it shows your name, your email and your plan. [built]
- While a notice is unread, the account mark carries a small amber dot, the amber of the coach's question; the dot goes when none is unread. [built] {R-0611}
- Under your name, one row, Notices, with the number unread as its figure, opens the Notices page: every notice you have been sent, newest first, each with its day and its first line; an unread one has the same amber dot before it. Tapping one opens the screen it points to and counts it read; one that points to the account view, its Notices, or nowhere has no arrow and a tap only counts it read, in place. There is no row until a notice has been sent. [built] {R-0611}
- Your profile page holds your first name, last name and birthdate. [built]
- There is a row for whether the coach speaks its replies out loud. [built]
- The same speaking switch appears once in the chat as a named shortcut, writing the same setting. [built]
- With it on, your phone's own voice reads each reply as it starts arriving, and sending the next message cuts it off. [built] {R-0099}
- A button under each coach reply plays it again, the way the Claude Code mobile app has one. [built] {R-0521}
- Which voice reads the replies is not settled: today it is your phone's own, which costs nothing, and a better-sounding paid one waits on Patrick. [open]
- No other setting appears in two places. [built]
- There is a row for how often the coach may message you first, and its choices read as a most, never a schedule: never, at most monthly, at most weekly. The line under it says never unless you ask, or never more than once a month (a week), and only when the coach notices a pattern in your family's events or follows up on something you agreed to. [built] {R-0004}
- The coach page has a row for bug reports: ask me, or always send. [built] {R-0056}
- There is a row for light, dark or matching your phone. [built]
- Your families are listed, with the number of sessions and when each was last used, and a tick on the one you are in. [built]
- Tapping a family opens it, and one is open at a time. [built] {R-0175}
- A search box appears in that list once you have six or more families. [built]
- Admins see a "Find a person" box at the top of that page: with the box empty the page shows only the admin's own diagrams; two or more letters show only the people whose email or name match, and the admin's own diagrams are hidden until the box is cleared; tapping a person slides in a page of its own titled with their name, listing their diagrams in the same rows, the way every page of the account view slides in; back slides it away to the search with the words and the people found as they were; tapping a diagram opens it read-only: one quiet line under the title row says "Viewing <name>'s diagram, read-only" with "Back to my diagram", which puts the app back on the admin's most recently used diagram. While it is open the record, the timeline, the chat history and the lists show, and the message box, Send, rename and delete, a question's actions, and a detail card's "Tap to comment…" are hidden; no tap is recorded and nothing is sent. It is never listed among the admin's own diagrams, and no sharing is granted. Nobody else sees the box. [built] (Patrick, 2026-10-01) {R-0630}
- Licences and the plan are listed; nothing on that page implies a price yet. [built]
- Auditors and admins see a Coding section above Sign out: Your coding task, which opens the one task card; Next meeting, for admins only, which opens the agenda; and Auditor's Coding Guide, which opens the concept pages on a page of its own. [built] {R-0265, R-0259, R-0541, R-0567}
- Admins also see a Quality section with one row, Better replies, over the line "Pick the better of two coach replies"; it opens the screen where two coach replies to the same words are picked blind, titled Better replies. [built] {R-0599}
- Better replies serves the pairs a conversation at a time, in the order the words were said, so a session reads as it happened; the conversation up to the words both replies answer stays above the two replies. [built] {R-0599}
- Each of those opens as a page of the account view, sliding in over it the way Coach, Appearance and Your Plan do, and the back arrow at the top left returns to the account view. [built] {R-0259, R-0265}
- A plain subscriber or a professional sees neither section. [built] {R-0311}
- Sign out sits alone at the bottom and signs you out immediately, with no confirmation step. [built]
- Every icon button in the app is the same size: a forty-four point target with a forty point mark inside it. [built] {R-0234}
- Admins and auditors see a Conversation Feedback switch on the Coach page. Turning it on asks first, in a dialog that says it adds cost and to turn it off when done; admins also see what it costs. [built] {R-0637, R-0642, R-0643}
- Conversation Feedback turns itself off 5 minutes after the latest of your turning it on, the coach's last reply and your last vote, and the page says when. [built] {R-0672}

## The about page

@frame built#f18 | Everything the record holds about one opened group, in words: why these events are one stretch, the years, and each event.

What it is for: what the app is, one level in from the picture.

- An "i" opens it, and a close mark takes the arrow's place while it is open. [built] {R-0234}
- It slides in over the picture the same way every other lower level does. [built] {R-0224}
- It is words, so no hint line is drawn under it. [built]
- Going back from it returns you to the whole line. [built]

## Addresses

What it is for: every screen and everything on it has its own web address, so the address bar says where you are, the back button steps back, and the coach, a notice or a link can take you anywhere in the app.

- The address bar changes as you move: opening the account view, one of its pages, the sessions drawer, the lists, an editor, the play-by-play or a coding screen is a new step the back button undoes. [built] {R-0055}
- Opening a cluster or picking an event on the picture changes the address without adding a step, so a reply that points at five things is not five presses of back. [built] {R-0055}
- Opening the app at any address, or signing in from one, lands there; an address that names something to light (a message, a session, a notice, a cut, a snapshot) scrolls it into the middle of its list and rings it the way a message is ringed when a moment traces back to it. [built] {R-0055}
- An address whose thing is gone says so in a short note and leaves the app where it could get to. [built] {R-0055}
- A notice may point at any address in the app as well as at the four screens it named before. [built] {R-0055, R-0611}
- When you ask the coach for help with the app, or ask to see something, it can take the app there while it answers; its reply then carries a line such as "Opened *the coach settings*" whose name is a chip that goes there again. It never moves the app during coaching otherwise. [built] {R-0055}

| address | what it opens |
|---|---|
| `/app/` | the chat, with the picture put down |
| `/app/chat/<message>` | the chat, scrolled to that message and ringed |
| `/app/sessions` | the sessions drawer |
| `/app/sessions/<session>` | the sessions drawer, with that session's row ringed |
| `/app/account` | the account view |
| `/app/account/profile`, `coach`, `appearance`, `diagrams`, `plan` | that page of the account view |
| `/app/account/notices` | the account view's Notices page |
| `/app/account/notices/<notice>` | the Notices page, with that notice ringed |
| `/app/account/coding-task` | your coding task |
| `/app/account/meeting` | Next meeting |
| `/app/account/meeting/<day>` | the page of the meeting on that day (`undated` for the one with no day) |
| `/app/account/meeting/<day>/<cut>` | that meeting's page, with that cut ringed |
| `/app/account/better-replies` | Better replies |
| `/app/account/literature-review` | Auditor's Coding Guide |
| `/app/cluster/<cluster>` | that cluster opened on the picture |
| `/app/event/<event>` | that event picked on the picture |
| `/app/event/<event>/edit` | the events list with that event's detail view open and its row ringed (the address of the parked editor, kept) |
| `/app/event/new` | the new-event form |
| `/app/person/<person>` | the people list with that person's card open and its row ringed (the address of the parked editor, kept) |
| `/app/person/new` | the new-person form |
| `/app/events`, `/app/people`, `/app/questions` | that list of the lists drawer |
| `/app/play/<message>` | the play-by-play that message keeps |
| `/app/play/<message>/<snapshot>` | that play-by-play at one snapshot, its caption ringed |
| `/app/coding/<coding>` | a coding screen |
| `/app/vote/<cut>` | the vote on that cut |
| `/app/meeting/<cut>` | the meeting run on that cut |
| `/app/result/<cut>` | what the meeting produced on that cut |
| `/app/guidelines` | the coding guidelines |

## When something goes wrong

@frame built#f19 | A message that did not go through: the notice sits where the reply would have been and stays until you tap try again.

What it is for: knowing what happened when a message does not go through.

- A message that does not go through leaves your words in the thread with a warning under them and a way to send them again. [built] {R-0182}
- The warning says which of three things happened: nothing came back, the server refused it, or the server broke. [built] {R-0182}
- The warning clears when the next attempt works, and comes back if it still applies. [built] {R-0182}
- Your words are only stored once the coach's answer lands, so sending again never stores them twice. [built]
- The coach's bubble is never left blank waiting. [built] {R-0184}
- A record edit the app cannot make on your behalf fails and says so rather than writing something invented. [built]

## Bug reports and feedback

What it is for: telling the people who make the app that something did not work for you, or what you want changed, without leaving the conversation.

- When you tell the coach the app or the coach went wrong (something did not work or did not update, the coach keeps repeating itself or misunderstood you, you correct the same thing in your record a second time, or you are frustrated with the app), the coach answers in one sentence and goes back to the conversation; once its reply is done, a sheet slides up from the bottom headed "Send this as a bug report?" with your words and the buttons "Send the report", "Always send" and "Don't send". The coach may also offer one about its own mistake when it sees it misread your record; then the words are its own. [built] {R-0056}
- During the beta, "Don't send" on the bug sheet is drawn faint and cannot be tapped, with the line "Disabled during the beta" under it: you choose between sending this once and always sending, never whether it is a bug, and a bug is never turned down. [built] {R-0613}
- When you tell the coach something you wish for or dislike about the app, the same sheet is headed "Send this as feedback?" with your own words and the buttons "Send the report" and "Not feedback". "Not feedback" stays live in the beta, for when the coach took something you said to it as feedback about the app. [built] {R-0056, R-0613}
- The sheet is always in full, never folded, and takes the focus itself, not a button. It comes up for each new thing you say, but never twice in one sitting for the same words (ignoring case and spaces at either end), whether you sent them or turned them down; this phone remembers them across a reload. [built] {R-0056}
- An error in the app's code never raises a sheet: the amber warning in the thread says what went wrong, and the error goes to Grafana. [built] {R-0056, R-0182}
- The sheet is modal: the thread behind it is dimmed and cannot be tapped until you answer it, and nothing is ever added to the thread. [built] {R-0056}
- The sheet and the card after it are as wide as a phone and at most 480 wide on a wider screen, centred at the bottom. [built] {R-0056}
- After Send, the sheet turns in place into "Your report was sent" with an OK button; it closes on OK or by itself after ten seconds. If the report cannot be sent, the same card says so and why. [built] {R-0056}
- "Always send" is kept in your settings: from then on a bug the coach offers is sent with no sheet and no card at all. Feedback still asks. [built] {R-0056}
- A report is one row in the reports table: sent, it keeps the words; turned down, only the turn and the message it came from. During the beta only feedback is ever turned down. [built] {R-0056, R-0613}

## On a desktop (Pro)

@frame built#f3 | The chat in a desktop window: the same screen, wider, with more room between the marks on the line.
@frame built#f13 | The events list in a desktop window.
@frame pro#f5 | The phone screen made wider: the drawer stays open beside the picture instead of sliding over it.

What it is for: the same app, wider, for professionals.

- It is one app on the phone and on the desktop, with features turned on by your licence, your role and which view you are in. [built] {R-0237}
- A wider screen pins the events and people drawer open on the right instead of sliding it over the chat. [built] {R-0243}
- That wider layout now comes up for anyone on a wide window, a phone turned on its side included, not only a professional. [built] {R-0367}
- A professional gets the same chat screen with things added to it, never a different app. [built] {R-0243}
- Nothing gets a new screen where an existing screen can carry it. [drawn] {R-0243}
- Nothing is ruled about how the existing desktop app fits in, and the chat app is not allowed to corner that decision. [open] {R-0081}
- Opening a record made in this app in the released desktop app has never been tried. [open]

## Cases (Pro)

@frame pro#f1 | The account page for a professional: the list of families is headed cases, and the tick says which one the app is on.
@frame pro#f2 | The chat screen for the case you switched to; the title row names the case you are on.

What it is for: a professional's several client records.

- A professional's cases are the same family switcher on the account page, not a new screen. [built] {R-0243}
- Each case has its own sessions and its own picture. [built] {R-0243}
- A client owns their own record and a clinician is granted access to it, so the record outlives the work they do together. [built] {R-0080}
- A note is a session of its own: the clinician talks to the coach about the case after the fact, the coach records what it hears, and the note is listed with the sessions and labelled as a note. [built] {R-0281}
- Notes can be coded in the IRR study exactly like chat sessions. [drawn] {R-0281}
- People and events keep a notes field in their editors, the same notes the desktop app already stores. [built] {R-0281}
- The drawn family diagram stays in the plan and arrives once auto-arrange proves itself on real data. [drawn] {R-0240, R-0281}

## The case report

What it is for: one screen to present your own record from, in the order the Bowen literature presents a case, opened from the icon in the title row at /app/case-report (Patrick's seminar, 16 October 2026). It reads the record the chat reads and draws again after every coach turn.

- It opens from an icon in the title row over the chat, and the coach opens it when asked; it is a full screen with a back arrow to the chat. [built] {R-0714}
- Every user can show the case report of the family the app is on; letting other people see it is for later. [built] {R-0715}
- Ten cards in the approved order: the coach's main guess, who is in the family, what brought the person, the couple since they met (or the person's parents and partners, stage by stage, when not married), each parent's own family, the coach's guess, the person's own part, where there was a choice, what to work on, the effort. The titles are the ones Patrick reviewed. [built] {R-0713, R-0716}
- A strip under the timeline has one item per card in the same order; a tap glides the cards to that card, rings it, and puts an open play-by-play away. [built] {R-0702}
- Text never folds and cards never collapse; only each side of the family folds. [built] {R-0689, R-0690}
- The timeline is pinned at the top; every chip lights what it names on it. A person's chip lights that person's events; a cluster's chip opens the cluster with explain offered, and explain opens the play-by-play of the cluster's own dated events. [built] {R-0696, R-0700}
- A coach's guess is the chat's own coach bubble, straight on the white card, with the dated facts it rests on as one-line chips under it; its "Coach" label lights them all. [built] {R-0698}
- The main guess, the own part, the choice and what to work on (up to three) are the guesses the coach put on those cards; the newest replaces the one before. The screen never picks a guess itself. [built] {R-0709, R-0713}
- A guess card the coach has put nothing on says in the coach's bubble that there is not enough in the record yet, and to chat more with the coach. A record card with nothing in it keeps its title and its book. [built] {R-0699, R-0710}
- The own part card shows the coach's guess and, once the person has answered the coach's question, the person's own words under their name as their own view. [built] {R-0708}
- The lines under the card titles are written by the app from the record: the person's place among brothers and sisters, how many events hold their symptoms, the couple, each parent, the sessions with the coach; dates stand only inside chips. [built] {R-0716}
- The couple card shows only for a marriage the picture draws solid, with no later separation or divorce and both partners alive. [built] {R-0694}
- The family picture opens from the family button on the phone and stands as a left column on a desktop, with the key under the person's family and under each side. No shading by coverage. [built] {R-0697, R-0705}
- Every card has a book button at its foot that raises the passages behind the card, word for word, read from the private corpus by the server; the strip has one for the order of the cards. [built] {R-0691, R-0692}
- No count line under a guess, no years band, no row of people squares, and no words of the screen's own about certainty. [built] {R-0693, R-0699, R-0703}
- A record the report cannot be drawn from shows the reason on the screen and in the console, never a blank page. [built] {R-0711}

## Upload a recording (Pro)

@frame pro#f3 | The sessions sheet gains one button for putting a recording in.
@frame pro#f4 | After the recording lands you say which voice is the clinician and which is the client, and give the date.

What it is for: getting a recorded session into the app as a conversation.

- Uploading a recording is an item in the sessions sheet, beside starting a new session. [built] {R-0243}
- Before the file picker, a sheet says that transcribing costs Alaska Family Systems money and to check with patrick@alaskafamilysystems.com first; its one button chooses the recording. [built] {R-0349}
- An empty session shows, where the bubbles will be, a heading and a line or two saying what to type, worded for what the session is — a note asks for the write-up of the session just had, a professional's session asks about the case, a personal session asks who is on your mind — and it goes on the first send. [built] {R-0350}
- With nothing dated on the record, the picture is one centred sentence, the timeline draws itself as you talk, and the row under it carries no hint. [built] {R-0351}
- On the wide layout the drawer is pinned open, so the list button under the picture is not shown. [built] {R-0352}
- After upload, a sheet asks who each speaker is, and the approved drawing of it stands. [built] {R-0243}
- Once mapped, the recording reads as a conversation like any other and can be coded. [built] {R-0267}
- Colleagues' earlier sessions come in through this same path. [drawn]

## Coding a conversation


What it is for: saying what each line of a conversation tells you happened, so we can agree on what the record should be.

@frame coding#f5 | Coding on a phone: the conversation up to the cut, your own words under the line you tapped, Done in the top bar.
@frame coding#f2 | The same on a desktop, with the events list pinned open on the right.
@frame coding#f7 | Tapping Done asks once and explains that your coding will be saved and submitted for the meeting.

- Coding is stage one of reaching agreement, and it is done blind: you never see anyone else's coding of that conversation until you press Done. [drawn] {R-0242, R-0250}
- Only a user with the auditor role is a coder; a professional licence holder and a plain subscriber open on the chat and never see the task card, the Coding section of the account page, the ballot or the meeting. [drawn] {R-0311}
- You are given one task at a time and never a list to choose from. [drawn] {R-0265}
- The task names the conversation, the point it is frozen at, how many turns are new since you last pressed Done, and roughly how long it will take. [drawn] {R-0267}
- One green button starts it, and under it is a faint record of the tasks you have already finished. [drawn] {R-0265}
- Starting opens the conversation as a thread you cannot type into. [drawn]
- You tap a line and it is outlined in green. [drawn]
- You then type, in your own words, what that line tells you happened. [drawn]
- A cheap scribe turns your words into an event in the record, and the line it wrote appears under your words. [drawn]
- The new event appears in the events drawer and lights in the picture as it lands. [drawn]
- If the scribe cannot tell which person you mean, nothing is written and one amber line asks which person, and you answer by typing again. [drawn]
- A faint hairline marks the last point that was already agreed, and everything below it is what this task is about. [drawn] {R-0267}
- Your own earlier coding of the turns above that line is shown as small marks; nobody else's is. [drawn] {R-0242}
- The bottom of the thread is marked with the point the conversation is frozen at, and turns after it are not shown at all. [drawn] {R-0267}
- Done ends the task, and the next single task card takes its place. [drawn] {R-0265}
- A task you cannot start yet is shown greyed with what it is waiting for, rather than leaving you an empty screen. [drawn]
- On a phone it is the same screen, with the drawer sliding over instead of pinned, and the sessions button giving way to Done. [drawn]
- A sentence about a marriage or a parent is written the same way, and the line under it reads "+ Marcus & Delphine · married · 1970" or "+ Corinne · daughter of Marcus & Delphine". [built] {R-0326}
- A bond or a birth the coder gives only one side of still gets written: the record adds the other as a generically named person. [built] {R-0325}
- A sentence naming two people is written as being about both of them, not just the one the line was tapped for. [built]
- A date the coder gave only as a year reads back as that year alone, never guessed down to a month. [built]
- Your own typed words stay in the thread under the line you coded, with the scribe's edit line beneath them, so the thread reads as a coding conversation. [drawn] {R-0270}
- Done sits in the top bar beside your account mark, never in the composer bar, so it cannot be mistaken for adding something. [drawn] {R-0271}
- Tapping Done asks once, in a sheet, and explains that your coding will be saved and submitted for the meeting and cannot be changed after that. [drawn] {R-0271}
- The box at the bottom and its send button belong to single codes only; they never submit the whole task. [drawn] {R-0271}
- There is no "coding" mark beside the title; Done in the top bar and the thread you cannot type into say what the screen is. [drawn] {R-0271}
- Turns before the last agreed point are shown in full, but tapping one only tells you that part was already agreed; coding happens only between that line and the frozen point. [drawn] {R-0271}
- Nobody is assigned; any coder may code any conversation at any time, and each finished coding joins the pool and recomputes the agreement figures. [drawn] {R-0242}
- Agreement is measured on the finished records, not on individual turns. [drawn] {R-0242}
- The coach's own pass over a conversation is one coding among the others and is hidden the same way. [drawn] {R-0242}
- Nobody is paid and there is no quota; the work is a rolling window and conversations keep growing. [drawn] {R-0251}
- The old coding page becomes a link marked as legacy and is deleted once its material has been coded again. [drawn] {R-0238}
- The coding screen's header shows the conversation's name. [built]
- The coding screen's list has no button for adding an event or a person; a coder adds one by tapping a line of the conversation and saying what happened. [built] {R-0663}

## Your one task


What it is for: Patrick choosing what gets coded, and everyone seeing one thing to do.

@frame coding#f1 | Your phone before a meeting: one card, one button, and under it what you have already finished.
@frame coding#f6 | After Done the next single card takes its place, greyed until Patrick opens the vote.
@frame review#f10 | Patrick's screen: the date, what is on the agenda, who is done, the button that opens the vote, and the agenda that fills itself.

- Patrick selects a cut inside the chat itself, never on a separate page. Next meeting's button, "Select a cut for the agenda", goes to the Diagrams page with the Find a person box empty and ready to type in, which opens anyone's diagram read-only. [built] {R-0629}
- On someone else's diagram the read-only line carries "Select a cut" beside "Back to my diagram". Tapping it puts an amber line under the read-only line, "Selecting a cut · tap the first line, then the last", with "cancel"; arriving from Next meeting's button it is already on. The message bar gives way to a foot bar, "Place this cut", grey until both ends are tapped. [built] {R-0629}
- From Next meeting's "Select a cut for the agenda", tapping the admin's own diagram on the Diagrams page, ticked or not, opens the admin's own chat with the same amber line, "cancel" and foot bar; the message box is hidden until cancel or placing. The admin's own chat has no standing "Select a cut". Tapping the open diagram without the button simply returns to its chat. [built] {R-0632}
- A cut is a first and a last line of the thread, in one sitting or across several. The first tap rings that line amber and the amber line reads "now tap the last line"; the second rings every line between, across the lines between sittings, fades the lines after the cut, and the amber line says what the cut spans, as "10 to 17 Mar, 2 sittings". A third tap starts over. [built] {R-0629}
- On someone else's diagram the sessions drawer only reads: tapping a sitting closes the drawer and scrolls the thread to that sitting's first line, and rename and delete are not offered. [built] {R-0629}
- Placing the cut returns to Next meeting. A newly placed cut joins the next meeting: the soonest meeting date on the agenda, or no date while none has one. [built] {R-0267, R-0629}
- A cut's row on Next meeting names the person whose diagram it is, then the days it spans with the year and how many sittings, as "10 to 17 Mar 2026 · 2 sittings". Tapping the row opens that cut in the family's thread, ringed, to move its lines; the cross takes it off before anyone has started. [built] {R-0629}
- No end of a cut can be placed at or before the last point that was already ratified. [built] {R-0267}
- A cut placed at the end of a finished conversation or recording takes in the whole thing, so a whole transcript is not a different kind of task. [drawn] {R-0267}
- Anything that changed since the last cut is coded again. [drawn] {R-0267}
- The agenda screen is the whole of Patrick's administration: the meeting date, what is on the agenda, and who is done. [drawn] {R-0259, R-0267}
- One meeting date is one meeting: the agenda shows each date once, its cuts under it, and, once the vote is open, one "run the meeting" button for it. A new date on a meeting moves all of its cuts. [built] {R-0250, R-0258}
- "run the meeting" opens that meeting's page: each cut with who has submitted a coding of it and who has not; a cut nobody has submitted says "No coder has submitted yet" under it, and a cut someone has submitted opens the room on it. [built] {R-0250, R-0258}
- Each coder's state is shown as not started, coding, done or voted, with a count of who is closed out. [drawn] {R-0258}
- One control nudges the people who are not done. [drawn] {R-0258}
- Taking a conversation off the agenda is the cross on its row, before anyone has started; the cross first asks "Take this cut off the agenda?" with the person and the days spanned, "Take it off" or "Keep it"; a tap outside or Escape keeps it. [built] {R-0631}
- The button that runs the meeting is the app's filled primary button, reads "run the meeting", and has the same room after it as before it. [built] {R-0341}
- Only an administrator sees the controls on this screen; a coder who reaches it sees the work but not the way to move it. [built] {R-0346}
- A ratified conversation keeps a row with a way in to the result; the row says where the cut stops and the day the room ratified it, so two cuts of one conversation read differently. [built] {R-0275}
- Every coder's single task card is derived from that screen. [drawn] {R-0265}
- Asking a coder to correct the coach's pass instead of coding from scratch was dropped, because coding is blind. [drawn] {R-0250}

## The vote before the meeting


What it is for: deciding as much as possible on your own phone, so the meeting only handles what is left.

@frame review#f1 | The vote on a phone, one disputed event per screen, the opinions shown without names.
@frame review#f2 | Choosing change: the editor opens prefilled so you can write an opinion none of the coders wrote.

- Once enough coders have finished, a ballot opens on each coder's phone. [drawn] {R-0250}
- The ballot shows one disputed event per screen. [drawn] {R-0257}
- Each screen shows the date, who it happened to, what happened, and the transcript line it came from. [drawn]
- The opinions are shown without names, so nobody defers to the most senior person in the room. [drawn] {R-0252}
- Nothing the coach or any other AI thinks is in the ballot at all. [drawn] {R-0254}
- Tapping an opinion votes for it exactly as written. [drawn] {R-0257}
- "Change" opens the app's own event editor over the ballot, prefilled, so you can write an opinion nobody wrote, and it joins the count as one more opinion. [drawn] {R-0257}
- "Drop" votes that this should not be an event in the record at all. [drawn] {R-0257}
- When any coder left the item out, a plain faint label says so — "2 coders left this event out" — never a row you can tap, because leaving it out is not a vote. [built] {R-0315}
- You may say why you voted as you did, and you may skip it. [drawn]
- An item you skip stays on your list until the ballot closes. [drawn]
- You can open the transcript at the line in question from the ballot. [drawn]
- Opening the transcript outlines the statement the version was written from, the way the coding screen does. [built] {R-0337}
- A version you have chosen is lit without a box drawn round its family picture. [built] {R-0337}
- "None" is the last choice in the relationship field, as it is for the three variables. [built] {R-0337}
- A prev button sits beside next, so a dot that moved you on can be walked back. [built] {R-0337}
- The transcript line and the session it came from stay attached to the event and are not edited here. [drawn]
- Names are hidden whenever anyone is voting; only the meeting shows who coded what. [drawn] {R-0272}
- The vote opens when Patrick opens it, never at a coder count. [drawn] {R-0273}
- No rule decides an item before the meeting; the vote's tallies inform the meeting and the meeting decides. [drawn] {R-0274}
- The same agreement timeline sits above the item you are voting on, with the event you are on enlarged in green. [drawn] {R-0278}
- People and bonds are on the ballot too, read before the events, because an event about somebody nobody has agreed on yet cannot be settled. [built] {R-0326}
- Each version of a person or a bond is drawn as a small family with that person in the middle, so two readings of who somebody's parents are read as two shapes. [built] {R-0326}
- "Change" on one of those opens the person's or the bond's own editor, the same one the record is corrected in. [built] {R-0326}
- When the matcher cannot tell which person of another coding a version is, the item says the room decides who is who and carries both versions. [built] {R-0326}

## The meeting


What it is for: closing what the vote could not, and ratifying the record.

@frame review#f11 | The meeting screen: every disputed event with its tally, most split first, and the timeline above showing agreed and disputed events.

- The meeting screen carries only the items the ballot left open. [built] {R-0250}
- Names and counts appear here for the first time. [built] {R-0252}
- The header is one title line — the word Meeting, the day, the conversation — then one line of labelled figures (how many events, how many disputed, what agreement was before the vote, how many people and bonds); no figure appears twice on the screen and the tally chip that read the margin as shorthand is gone. [built] {R-0321, R-0340}
- The title and the figures scroll away with the list, but the wire, the three colours of the wire with one word each, and the ordering control stay at the top of the scrolling area as one compact band, so the room can always reach another event; the ratify bar stays at the bottom. [built] {R-0340}
- The list is read either most split first or in the order the events happened; sorted by time every event is in one list, the agreed ones marked agreed. [built] {R-0316}
- An item the vote agreed on opens the same card as a disputed one on a tap of its row, with a close button at its top right; keeping is disabled once it is kept, and change and mark unresolved stay. [built] {R-0317}
- Every row names who and what; an event with no date says it has no date yet, and an item with no description is named by its kind in words. [built] {R-0318}
- On a split, tapping a version keeps it and the row lights, the way an opinion is chosen on the ballot; no separate keep button. [built] {R-0319, R-0339}
- Every dot on the wire answers a tap, on the meeting as on the ballot: it puts the room on that event and brings its card up. [built] {R-0320}
- The list travels to that card rather than jumping to it, so the room sees which way it moved. [built] {R-0341}
- A choice made on an item never moves it: it stays where the sort put it, collapses to one line saying the words of the version the room kept or that it was left unresolved, and tapping that line opens the card again with the choice lit. Only the sort control orders the list again. [built] {R-0341}
- Every open item must be given one of three choices: keep a version, change it, or mark it unresolved. [built] {R-0257}
- The ratify button stays dead until every open item has a choice, and says how many still need one. [built] {R-0257}
- Each choice made in the meeting is a decision, and only decided events feed the coding guidelines; plenty stay unresolved for a while, and that is expected. [built] {R-0309}
- An item marked unresolved is kept as data and left out of the agreed record. [built] {R-0250}
- Ratifying takes about eleven seconds while the AI drafts the guideline rules from the decisions, and that wait is accepted. [built] {R-0313}
- The screen shows the agreement figures from the first pass. [built]
- How much of the meeting is left is shown beside them; the app holds the meeting as a day and not a time, so there is nothing yet to count down from. [drawn]
- The event in front of the room is shown on the picture as well as in the list. [built]
- Only events that are new or changed since the last ratified cut are in dispute; earlier ones stand unless a new turn reopened one. [drawn] {R-0267}
- Convergence is required but nobody is forced to converge, and deciding a whole kind of disagreement with one rule is one of the tools for getting there. [drawn] {R-0251}
- Each meeting tries an approach and teaches the next one; there is no review before the meeting beyond the ballot. [drawn] {R-0244, R-0250}
- The two-sided comparison of two codings already drawn has to fold into either the ballot or this screen, and where is unbuilt work. [drawn]
- The review screens are built as their own isolated piece, so changing them can never break the chat or the professional features. [drawn] {R-0245}
- The meeting sees every disputed event with its tally, the most split first, and the unanimous ones collapsed below. [built] {R-0274}
- People and bonds are in the meeting's list, read before the events, each version its own row with its own drawing. [built] {R-0326}
- Tapping a version's row keeps that version, and the kept row lights the way a chosen opinion lights on the ballot; tapping another version changes the choice, and tapping the kept one does nothing. [built] {R-0339}
- Under the versions are the two other choices, "change…" and "mark unresolved". [built] {R-0339}
- A version row carries the initials of the coders who wrote it and no count. [built] {R-0342}
- Structure cards are laid out like the event cards: the version rows and the family picture line up the same way. [built] {R-0338}
- Work on the screens goes on while the meeting screen is being read; a page reloading under you is accepted. [built] {R-0338}
- They are not on the wire: the wire stays one dot per event, and how many people and bonds the cut holds is a count on the header's line of figures. [built] {R-0326, R-0340}
- One timeline above the list shows agreement and disagreement at a glance: one dot per event, teal where the vote agreed, amber where it did not, with a small count beside a disputed dot. [built] {R-0277, R-0278}

## After ratification


What it is for: what the meeting produced, with nothing left to choose.

@frame review#f13 | The result screen: what was ratified, the guideline changes the AI wrote, where it disagreed with the room, and what each coder tends to do.
@frame review#f15 | The coding guidelines inside the app, always current, each rule with the decision it came from and a flag link.
@frame review#f14 | Where you find them: tap the (i) at the top of the coding screen and the guidelines slide in over your coding.

- The result screen shows how many events were ratified and how many were left unresolved. [built]
- It shows agreement before the ballot and after ratification, side by side. [built]
- One more count says how many people and bonds the room ratified and how many it left open; an unresolved person is the one that matters most, because every event about them stands on it. [built] {R-0326}
- It shows how the coach's own pass scored against the agreed record. [built] {R-0242}
- When the coach never coded that conversation, the screen says so in both places rather than leaving the score and the differences blank. [built]
- The top summary moves with the page instead of staying fixed, and is laid out as a heading, then one line of labelled numbers, then the sections below, not raw monospace text. [built] {R-0344}
- The result can be opened again after you leave it: from a coder's finished tasks and from the agenda for a ratified conversation. [built] {R-0343}
- A coder's finished tasks look tappable and open their meeting's result; they are never greyed like rows you cannot use. [built] {R-0344}
- The word for the agreed record is ratified; what the coach proposes is a proposal and is never called gold. [drawn] {R-0249}
- The AI writes the guideline changes itself out of what the room decided, and they are live; there is nothing to choose on this screen. [built] {R-0259, R-0310}
- Each new rule shows the decided item it came from and the margin it was decided by. [built] {R-0259}
- Where the AI's reading differed from the room is listed afterwards, with its reason, as an audit rather than a vote. [built] {R-0254}
- What each coder tends to do differently from the others is shown. [built]
- Every vote, decision and ratification is a row in the app's own tables with who did it and when. [drawn] {R-0262}
- How last year's coding material is carried over is a choice Patrick has not made; the plan under consideration keeps the rules and the agreement tables as rows and the written deliberations as text. [open] {R-0262}
- Every rule the AI wrote carries a "flag for next meeting" link, and flagged rules go on the next meeting's agenda by themselves; an event the room left unresolved stays unresolved as data and is never brought back to a later meeting; who has not finished a coding is the coder list's own line, not the agenda's. [built] {R-0276, R-0308, R-0312}
- Only an administrator sees the "flag for next meeting" link, and tapping it again takes the flag off; anyone else sees a flagged rule said as text rather than a link. [built] {R-0346}
- Only an administrator puts a conversation on the agenda, moves the cut, opens the vote or runs the meeting; a coder never does. [built] {R-0346}
- The meeting's results are rows in the database — codings, votes, decisions, rules with the decision each came from — so everything is traceable; the coding guidelines are the one written output. [drawn] {R-0275}
- Anyone can read the current coding guidelines inside the app from an (i) button at the top of the coding screen. [drawn] {R-0275, R-0278}
- The coding guidelines file in the code is generated from the rules the app holds and is never edited by hand. [drawn] {R-0275}
