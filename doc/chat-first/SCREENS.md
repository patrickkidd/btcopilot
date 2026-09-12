# Family Diagram — what every screen does

This is the current truth about every screen in the app and how it behaves, written for the
people who are about to use it rather than for the people building it. Each line is one
behaviour, tagged `[built]` if it is in the app today, `[drawn]` if it is approved on a drawing
but not built, and `[open]` if it is a choice Patrick has not made yet. It is rewritten as
decisions land; the exact sizes and colours live in the internal interface spec, not here.

Updated: 2026-09-12

---

## Signing in

@frame built#f1 | Signed out: the app name, the address you are signing in as, and one button.

What it is for: getting into the app without a password.

- You get an emailed link and tapping it signs you in, so there is no password to make or remember. [built]
- Signing in with an emailed code also creates the account, so there is no separate sign-up step. [built]
- A sign-in lasts about six months, so you rarely sign in twice on the same phone. [built]
- After the first sign-in the app offers to let you use Face ID or a fingerprint instead, and asks only once per phone. [built]
- If you say no to Face ID it waits a month before offering again. [built]
- On a phone the app offers, once, to add itself to your home screen, and shows the exact button to tap. [built]
- If you dismiss the home-screen card it comes back no sooner than a week later. [built]
- The card never blocks the conversation; you can ignore it and keep typing. [built]
- Signed out, you see the app name, who you are signing in as, and one button to sign in. [drawn]
- Invite links sent for review use the machine name rather than a numeric address, so they open on a phone. [built] {R-0234}
- The app is called Family Diagram wherever you can see it. [built] {R-0216}

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
- Three dots appear in the coach's bubble the moment you send, so the bubble is never blank while it thinks. [built] {R-0184}
- The thread stays at the bottom on the newest words while the coach types. [built] {R-0172, R-0231}
- Opening the app again puts you at the bottom of the thread, on the newest words. [built] {R-0231}
- Everything the app says can be selected and copied, including the coach's replies and the lines about what it changed. [built] {R-0183}
- The first time you open it, the coach says it is there whenever you want to think out loud about your family and asks who is on your mind. [built]
- Sending a second message while the coach is still answering does nothing, so your words are never stored twice. [built]
- The coach does not message you first unless you ask it to. [built] {R-0017}
- Correcting something in conversation changes the record in place, and older references still point at the right thing. [built]
- You can also undo the last thing the coach did by telling it to. [built]

## The picture at rest

@frame built#f5 | One event on the line: a single dot, no box around it.
@frame built#f6 | A dense record: events that belong together are boxes on the line, each showing how many it holds.
@frame built#f4 | A brand new record: nothing is on the line yet, with an amber question mark where the record has something to ask.

What it is for: the one picture, always above the chat, that is the app's memory of your family.

- One picture sits pinned above the chat and never appears and disappears. [built] {R-0002}
- It keeps a fixed height whatever it is showing, so the chat below it never jumps. [built] {R-0210}
- At rest it shows your clusters over time on one line: a horizontal line with marks on it and nothing else. [built]
- Only three kinds of mark exist at this size: the line, the marks on it, and an amber question mark. [built] {R-0005}
- The band under the picture reads "tap a cluster" when nothing is picked. [built]
- Tapping a mark once shows its words; nothing is sent to the coach and it costs you nothing. [built] {R-0073}
- Tapping it again sends it to the coach as something you are asking about. [built] {R-0072, R-0073}
- Tapping empty space, or the picture's own name, puts the picture down and clears what was picked. [built]
- A picked event shows its date and its own words in two lines above the line, and the year is written once under the mark. [built] {R-0210, R-0235}
- A picked loose event that is not in any cluster reads exactly like a picked event inside a cluster. [built] {R-0235}
- Tapping the words of the event already picked jumps to where it was coded in the chat. [built] {R-0192}
- An amber question mark appears where the record has a question, and only in three situations: an order it cannot tell, an open state it cannot confirm, and facts with no date at all. [built] {R-0005}
- Facts with no date sit on a shelf at the end of the line rather than being placed on it. [built] {R-0013}
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

- Tapping a cluster opens it, and the opened cluster slides in from the right over the whole line like a card. [built] {R-0224, R-0230}
- The card it slides in on has its own background, so it reads as a card and not as words over words. [built] {R-0230}
- The grey line above the picture becomes the name of what you are looking at, with a back arrow beside it. [built] {R-0223}
- Tapping either the name or the back arrow goes up one level. [built] {R-0223}
- An open cluster shows its name and the reason it is a cluster, never a list of its events, because a cluster can hold fifteen. [built] {R-0213}
- The events inside stay as marks; tapping one shows its words. [built] {R-0213}
- A cluster needs at least three events to exist. [built] {R-0215}
- Grouping is the coach's judgement, made from what you say as you say it; every grouping carries a one-line reason that says what is in it and what is not; the automatic grouping is only a first draft the coach may overwrite. [drawn] {R-0287}
- A stored cluster carries only its name, its reason, where it came from, and the events in it. [built] {R-0205}
- The coach may group and name events but may never invent an event to put in one. [built] {R-0076}
- The word for these is clusters, in the app and in the code. [built] {R-0197}
- Whether tapping an event's words inside an open cluster should jump straight to its editor is unconfirmed, and Patrick will say after testing it. [open] {R-0207}

## The play-by-play

@frame built#f9 | The board playing the first move: the people on a ring, the move drawn in green, and one sentence saying who did what.

What it is for: a play-by-play of what people did, one move at a time.
@link https://claude.ai/code/artifact/c523a1c9-b298-49e8-807b-142a8a7470f7 | The ratified move language: every relationship move and variable shift, animated, as the board plays them.

- The board is reached from the picture by the play mark alone, with no words beside it. [built]
- The board grows to fit what it is showing rather than sitting at a fixed height. [built] {R-0173}
- It draws the people involved on a simple ring and the moves between them, not your family's real layout. [built]
- The family will eventually be drawn as more than a circle of people, and you will never have to arrange it by hand. [drawn] {R-0187}
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
- A chip is the one visual that means "this puts words in the chat", so nothing else ever costs you a turn. [built] {R-0073}
- Chips are one size and show their whole label; they are never cut short and never expand. [built] {R-0169}
- Labels are kept short where they are written rather than trimmed afterwards, and the coach is asked once to shorten an over-long one. [built] {R-0169}
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
- The button sits inside the picture's own frame, matching the sessions button beside the chat input. [built] {R-0198}
- Events are grouped under their cluster, with a heading that stays in view as you scroll so you always know which cluster you are in. [built]
- A cluster of one event reads "1 event", not "1 events". [built]
- Events with no date are grouped under their own heading. [built]
- The lists can be searched. [built]
- Each row shows what happened on one line and the date and people on a second. [built]
- A row's summary uses short codes rather than running off the side of the phone. [built]
- The scrollbar is never covered by a cluster heading. [built] {R-0218}
- Tapping a row opens the editor for that item in place. [built]
- The line saying you can also edit by chatting was removed from these lists. [built] {R-0219}
- There is a button to add an event. [built]
- Editing by hand is possible but is not what the app is being tested on. [built]

## The event editor

@frame built#f14 | One event opened for correction by hand: its kind, who it happened to, its words, its date and how sure the date is.

What it is for: correcting or adding one event by hand.

- The editor holds everything an event carries: its kind, the people on it, a summary, details, where it happened, when, an optional end, and how sure you are. [built]
- Its fields are big enough to tap comfortably. [built] {R-0174}
- The kinds are shift, birth, adopted, bonded, married, separated, divorced, moved and death. [built]
- How sure you are is one of unknown, approximate or certain. [built]
- Symptom, anxiety and functioning are each set to up, down, same or not said. [built]
- A relationship change sits at the same level as those three, under one heading, never in its own section. [built]
- A relationship change is a kind plus the people involved, from the person who moved to the people it was aimed at. [drawn]
- The list of people a relationship points at is labelled differently by kind, so a conflict asks for the others and an overfunctioning asks who was underfunctioning. [drawn]
- A third list of people appears only for the inside and outside positions of a triangle. [drawn]
- The shift fields and the relationship field only appear for a shift; the spouse field only for a bonding, marriage, separation or divorce; the child field only for a birth or adoption. [drawn]
- Saving drops values that no longer apply to the kind, so changing a shift into a death clears the shift values. [built]
- Saving re-sorts the list by time and redraws the lists and the picture. [built]
- Delete appears only when you are editing something that already exists. [built]
- The relationship fields and the hiding of fields by kind are the unbuilt part of this screen; no decision is needed, only the work. [drawn]

## The person editor

@frame built#f15 | A person opened the same way: a name, a kind, and a line saying births and deaths come from talking to the coach.

What it is for: one person's own details.

- The person's kind field is labelled Kind rather than sex, to keep the category right. [built] {R-0200}
- A person carries buttons to their birth and their death when those exist, jumping to that event's editor. [built] {R-0201}
- The jump works in reverse, from an event back to the person. [built] {R-0201}
- Your own birthdate anchors your own line on the picture. [built]
- Every diagram that ever had a chat on it carries a person called Assistant, which is a defect and not yet fixed. [built]

## The sessions sheet

@frame built#f16 | Your past conversations, newest first, with one button to start a new one.

What it is for: your past conversations.

- A button beside the chat input opens a sheet holding your past sessions. [built]
- The sheet rises from the input bar and can be dragged back down to close. [built]
- Sessions are searchable by their titles, their summaries and the family they belong to. [built]
- Each row shows a title, the coach's one-line summary of that session, and when it was. [built]
- Rows are grouped under today, yesterday, this week, this month, and then by month. [built]
- The coach titles a session after the first exchange, and you can rename it by hand. [built]
- A session you renamed by hand is marked as such. [built]
- Emptying a rename puts the coach's own title back and says so. [built]
- The session you are in is marked. [built]
- Newest activity is first, and the order never changes while you are looking at it. [built]
- A button at the foot starts a new session, and refuses while the current one is still empty. [built]
- With no sessions at all it says past conversations collect here. [built]
- When you have several families, sessions are grouped under the family they belong to, each showing its three most recent. [built]
- Sessions are started from within the case you are on; there is no "+" beside other cases in the sessions sheet, and a personal user never sees the word case at all. [built] {R-0285}
- Someone else's session is simply not found rather than refused, so the app never confirms a session it will not show you. [built]
- The history in the review database is kept across code changes rather than reset. [built] {R-0191}
- Existing diagrams and conversations made before this app must open in it as sessions; old training transcripts are kept out of the list. [built]
- Clearing a record's coding and re-running the coach over the same conversation is a feature still to build. [drawn]
- After such a re-run, chips in the old thread point at events that no longer exist and read as plain words; the re-run is meant to re-link the ones that match. [drawn]

## The account page

@frame built#f17 | Your name and address, the coach and appearance settings, your records and plan, and signing out.

What it is for: you, your families, your plan, and signing out.

- Your account is reached by the mark at the top right of the title row. [built]
- That mark has no circle drawn around it, because there is no room. [built] {R-0222}
- Tapping it slides the account page smoothly over the app rather than making the app disappear. [built] {R-0225}
- The account page is a list where each row opens its own page with a back arrow, like the phone's own settings. [built]
- The top of it shows your name, your email and your plan. [built]
- Your profile page holds your first name, last name and birthdate. [built]
- There is a row for whether the coach speaks its replies out loud. [built]
- The same speaking switch appears once in the chat as a named shortcut, writing the same setting. [built]
- No other setting appears in two places. [built]
- There is a row for how often the coach may message you first, and it says the coach never messages first unless you ask. [built]
- There is a row for light, dark or matching your phone. [built]
- Your families are listed, with the number of sessions and when each was last used, and a tick on the one you are in. [built]
- Tapping a family opens it, and one is open at a time. [built] {R-0175}
- A search box appears in that list once you have six or more families. [built]
- Licences and the plan are listed; nothing on that page implies a price yet. [built]
- Sign out sits alone at the bottom and signs you out immediately, with no confirmation step. [built]
- Every icon button in the app is the same size: a forty-four point target with a forty point mark inside it. [built] {R-0234}

## The about page

@frame built#f18 | Everything the record holds about one opened group, in words: why these events are one stretch, the years, and each event.

What it is for: what the app is, one level in from the picture.

- An "i" opens it, and a close mark takes the arrow's place while it is open. [built] {R-0234}
- It slides in over the picture the same way every other lower level does. [built] {R-0224}
- It is words, so no hint line is drawn under it. [built]
- Going back from it returns you to the whole line. [built]

## When something goes wrong

@frame built#f19 | A message that did not go through: the notice sits where the reply would have been and stays until you tap try again.

What it is for: knowing what happened when a message does not go through.

- A message that does not go through leaves your words in the thread with a warning under them and a way to send them again. [built] {R-0182}
- The warning says which of three things happened: nothing came back, the server refused it, or the server broke. [built] {R-0182}
- The warning clears when the next attempt works, and comes back if it still applies. [built] {R-0182}
- Your words are only stored once the coach's answer lands, so sending again never stores them twice. [built]
- The coach's bubble is never left blank waiting. [built] {R-0184}
- A record edit the app cannot make on your behalf fails and says so rather than writing something invented. [built]

## On a desktop (Pro)

@frame built#f3 | The chat in a desktop window: the same screen, wider, with more room between the marks on the line.
@frame built#f13 | The events list in a desktop window.
@frame pro#f5 | The phone screen made wider: the drawer stays open beside the picture instead of sliding over it.

What it is for: the same app, wider, for professionals.

- It is one app on the phone and on the desktop, with features turned on by your licence, your role and which view you are in. [built] {R-0237}
- A wider screen pins the events and people drawer open on the right instead of sliding it over the chat. [built] {R-0243}
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

## Upload a recording (Pro)

@frame pro#f3 | The sessions sheet gains one button for putting a recording in.
@frame pro#f4 | After the recording lands you say which voice is the clinician and which is the client, and give the date.

What it is for: getting a recorded session into the app as a conversation.

- Uploading a recording is an item in the sessions sheet, beside starting a new session. [built] {R-0243}
- After upload, a sheet asks who each speaker is, and the approved drawing of it stands. [built] {R-0243}
- Once mapped, the recording reads as a conversation like any other and can be coded. [built] {R-0267}
- Colleagues' earlier sessions come in through this same path. [drawn]

## Coding a conversation


What it is for: saying what each line of a conversation tells you happened, so we can agree on what the record should be.

@frame coding#f5 | Coding on a phone: the conversation up to the cut, your own words under the line you tapped, Done in the top bar.
@frame coding#f2 | The same on a desktop, with the events list pinned open on the right.
@frame coding#f7 | Tapping Done asks once and explains that your coding will be saved and submitted for the meeting.

- Coding is stage one of reaching agreement, and it is done blind: you never see anyone else's coding of that conversation until you press Done. [drawn] {R-0242, R-0250}
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

## Your one task


What it is for: Patrick choosing what gets coded, and everyone seeing one thing to do.

@frame coding#f1 | Your phone before a meeting: one card, one button, and under it what you have already finished.
@frame coding#f6 | After Done the next single card takes its place, greyed until Patrick opens the vote.
@frame review#f10 | Patrick's screen: the date, what is on the table, who is done, the button that opens the vote, and the agenda that fills itself.

- Patrick opens the sessions sheet like anyone else, swipes the conversation he wants, and taps to put it on the table. [drawn] {R-0267}
- That opens the conversation so he can place the cut: the point everyone codes up to. [drawn] {R-0267}
- The cut starts at the last turn, and tapping any line moves it there. [drawn] {R-0267}
- The cut can never be moved back past the last point that was already ratified. [drawn] {R-0267}
- Turns after the cut are dimmed and wait for a later cut. [drawn] {R-0267}
- A cut placed at the end of a finished conversation or recording takes in the whole thing, so a whole transcript is not a different kind of task. [drawn] {R-0267}
- Anything that changed since the last cut is coded again. [drawn] {R-0267}
- The table screen is the whole of Patrick's administration: the meeting date, what is on the table, and who is done. [drawn] {R-0259, R-0267}
- Each coder's state is shown as not started, coding, done or voted, with a count of who is closed out. [drawn] {R-0258}
- One control nudges the people who are not done. [drawn] {R-0258}
- Taking a conversation off the table is one tap, before anyone has started. [drawn]
- Every coder's single task card is derived from that screen. [drawn] {R-0265}
- Asking a coder to correct the coach's pass instead of coding from scratch was dropped, because coding is blind. [drawn] {R-0250}

## The vote before the meeting


What it is for: settling as much as possible on your own phone, so the meeting only handles what is left.

@frame review#f1 | The vote on a phone, one disputed event per screen, the takes shown without names.
@frame review#f2 | Choosing change: the editor opens prefilled so you can write a take none of the coders wrote.

- Once enough coders have finished, a ballot opens on each coder's phone. [drawn] {R-0250}
- The ballot shows one disputed event per screen. [drawn] {R-0257}
- Each screen shows the date, who it happened to, what happened, and the transcript line it came from. [drawn]
- The takes are shown without names, so nobody defers to the most senior person in the room. [drawn] {R-0252}
- Nothing the coach or any other AI thinks is in the ballot at all. [drawn] {R-0254}
- Tapping a take votes for it exactly as written. [drawn] {R-0257}
- "Change" opens the app's own event editor over the ballot, prefilled, so you can write a take nobody wrote, and it joins the count as one more take. [drawn] {R-0257}
- "Drop" votes that this should not be an event in the record at all. [drawn] {R-0257}
- A count of coders who left the item out is shown, but leaving it out is not a vote. [drawn]
- You may say why you voted as you did, and you may skip it. [drawn]
- An item you skip stays on your list until the ballot closes. [drawn]
- You can open the transcript at the line in question from the ballot. [drawn]
- The transcript line and the session it came from stay attached to the event and are not edited here. [drawn]
- Names are hidden whenever anyone is voting; only the meeting shows who coded what. [drawn] {R-0272}
- The vote opens when Patrick opens it, never at a coder count. [drawn] {R-0273}
- No rule settles an item before the meeting; the vote's tallies inform the meeting and the meeting settles. [drawn] {R-0274}
- The same agreement timeline sits above the item you are voting on, with the event you are on enlarged in green. [drawn] {R-0278}

## The meeting


What it is for: closing what the vote could not, and ratifying the record.

@frame review#f11 | The meeting screen: every disputed event with its tally, most split first, and the timeline above showing agreed and disputed events.

- The meeting screen carries only the items the ballot left open. [built] {R-0250}
- Names and counts appear here for the first time. [built] {R-0252}
- The items the vote settled are listed separately and are not read aloud, each with a way to reopen it. [built]
- Every open item must be given one of three choices: keep a take, change it, or mark it unresolved. [built] {R-0257}
- The ratify button stays dead until every open item has a choice, and says how many still need one. [built] {R-0257}
- An item marked unresolved is kept as data and left out of the agreed record. [built] {R-0250}
- The screen shows the agreement figures from the first pass. [built]
- How much of the meeting is left is shown beside them; the app holds the meeting as a day and not a time, so there is nothing yet to count down from. [drawn]
- The event in front of the room is shown on the picture as well as in the list. [built]
- Only events that are new or changed since the last ratified cut are in dispute; earlier ones stand unless a new turn reopened one. [drawn] {R-0267}
- Convergence is required but nobody is forced to converge, and settling a whole kind of disagreement with one rule is one of the tools for getting there. [drawn] {R-0251}
- Each meeting tries an approach and teaches the next one; there is no review before the meeting beyond the ballot. [drawn] {R-0244, R-0250}
- The two-sided comparison of two codings already drawn has to fold into either the ballot or this screen, and where is unbuilt work. [drawn]
- The review screens are built as their own isolated piece, so changing them can never break the chat or the professional features. [drawn] {R-0245}
- The meeting sees every disputed event with its tally, the most split first, and the unanimous ones collapsed below to confirm or reopen. [built] {R-0274}
- One timeline above the list shows agreement and disagreement at a glance: one dot per event, teal where the vote agreed, amber where it did not, with a small count beside a disputed dot. [built] {R-0277, R-0278}

## After ratification


What it is for: what the meeting produced, with nothing left to choose.

@frame review#f13 | The result screen: what was ratified, the guideline changes the AI wrote, where it disagreed with the room, and what each coder tends to do.
@frame review#f15 | The coding guidelines inside the app, always current, each rule with the settle it came from and a flag link.
@frame review#f14 | Where you find them: tap the (i) at the top of the coding screen and the guidelines slide in over your coding.

- The result screen shows how many events were ratified and how many were left unresolved. [built]
- It shows agreement before the ballot and after ratification, side by side. [built]
- It shows how the coach's own pass scored against the agreed record. [built] {R-0242}
- The word for the agreed record is ratified; what the coach proposes is a proposal and is never called gold. [drawn] {R-0249}
- The AI writes the guideline changes itself out of what the room settled, and they are live; there is nothing to choose on this screen. [built] {R-0259}
- Each new rule shows the settled item it came from and the margin it was settled by. [built] {R-0259}
- Where the AI's reading differed from the room is listed afterwards, with its reason, as an audit rather than a vote. [built] {R-0254}
- What each coder tends to do differently from the others is shown. [built]
- Every vote, settlement and ratification is a row in the app's own tables with who did it and when. [drawn] {R-0262}
- How last year's coding material is carried over is a choice Patrick has not made; the plan on the table keeps the rules and the agreement tables as rows and the written deliberations as text. [open] {R-0262}
- Every rule the AI wrote carries a "flag for next meeting" link, and flagged rules, unresolved events and unfinished tasks go on the next meeting's agenda by themselves. [built] {R-0276}
- The meeting's results are rows in the database — codings, votes, settles, rules with the settle each came from — so everything is traceable; the coding guidelines are the one written output. [drawn] {R-0275}
- Anyone can read the current coding guidelines inside the app from an (i) button at the top of the coding screen. [drawn] {R-0275, R-0278}
- The coding guidelines file in the code is generated from the rules the app holds and is never edited by hand. [drawn] {R-0275}
