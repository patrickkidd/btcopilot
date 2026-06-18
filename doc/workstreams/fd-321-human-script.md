# FD-321 Human Walkthrough: Welcome Setup & Profile (cross-app)

This walk uses TWO apps that share ONE sandbox backend (the same server, the same logged-in user): the **Personal app** and the **Pro app**. The Personal app owns the first-launch Welcome wizard, the Settings "Profile" editor, the chat speaker label, and the account drawer (the hamburger menu at the top-left). The Personal app does NOT draw the family diagram, so you cannot see your diagram node there. The **Pro app**, opened against the SAME backend as the same user, is the ONLY place you SEE the diagram node with your name. The Pro app loads the server's current version at the moment you open the diagram and does NOT live-update while another app is editing — so after you save in the Personal app, you must open the free diagram in the Pro app to see the change, and if the Pro app already had it open, close it and open it again.

The bet you are judging — the **cross-app identity spine**: your identity, captured ONCE in the Personal-app Welcome wizard, stays consistent on the Pro-rendered diagram node, the Personal chat speaker label, and the account drawer. If that single source of "who the user is" holds, later Personal-app work can safely assume "the diagram node = the account holder" without rework.

**Go / no-go judgment (yours alone):** the Welcome setup and the Settings Profile flow look and feel right, and they correctly describe YOU on YOUR real diagram across both apps. A machine already confirmed every mechanical behavior — you are judging the holistic feel and that the name is actually you, everywhere.

## Main path

### A1 — First launch shows Welcome (Personal app)
Arrange:
- Start from a brand-new, empty profile with nothing set up yet, on the shared backend.
Act:
- Launch the Personal app.
Assert:
- The Welcome setup screen appears on first launch.
- A First name field and a Last name field are present.
- A birth date field is present.
- The Get Started button and the Skip for now link both appear.

### A2 — Enter your name and check Tab order (Personal app)
Arrange:
- The Welcome screen is showing with the First name field empty.
Act:
- Click the First name field and type your real first name, press Tab, type your real last name, then press Tab again.
Assert:
- Your first name shows in the First name field.
- Your last name shows in the Last name field.
- The first Tab moved focus to Last name and the second Tab moved focus to the birth date field, in that order.

### A3 — Set your birth date with the date control (Personal app)
Arrange:
- Your first and last name are filled in and focus is on the birth date field.
Act:
- Click the birth date field to open the date picker, then set your real birth date.
Assert:
- The same date picker used elsewhere in the app appears.
- Your chosen birth date shows in the birth date field once you set it.

### A4 — Finish setup with Get Started (Personal app)
Arrange:
- Your first name, last name, and birth date are all filled in.
Act:
- Click Get Started.
Assert:
- The Welcome screen does not stay on screen — it goes away.
- The main Personal-app view appears.
- The hamburger menu (top-left) is present.

### A5 — See your node on the diagram (Pro app)
Arrange:
- You finished setup in the Personal app, and the Pro app is logged in as the same user against the same backend.
Act:
- In the Pro app, open the free diagram — if it was already open from before, close it and open it again so it reloads the server's current version.
Assert:
- Your own node appears on the diagram showing your name.
- Your node displays your birth date.
- The node does not show a blank name or "Client".

### A6 — The spine: the same name in both apps
Arrange:
- The free diagram is open in the Pro app and shows your node.
Act:
- In the Personal app, open the chat and read the speaker label next to your own messages, then open the hamburger menu (top-left) to reveal the account drawer.
Assert:
- The diagram node in the Pro app shows your name.
- The chat speaker label in the Personal app shows your name and does not show "Client".
- The account drawer in the Personal app shows your name.
- The Pro-app diagram node, the Personal-app chat label, and the account drawer all display the SAME name.

### A7 — Edit the name in Settings Profile (Personal app)
Arrange:
- The account drawer is open in the Personal app and shows your name.
Act:
- Open the Profile editor from the account drawer, change the name (for example, fix a spelling), click Save, open the chat and the account drawer again, and in the Pro app close the free diagram and open it again.
Assert:
- The Profile editor displays your current first and last name when it opens.
- The account drawer shows the updated name after saving.
- The chat speaker label shows the updated name.
- Your node on the re-opened Pro-app diagram shows the updated name.

### A8 — Persistence across a real restart (Personal app)
Arrange:
- Setup is finished and your name is set.
Act:
- Fully quit the Personal app, then restart it.
Assert:
- After restart, the Welcome setup screen does not reappear.
- Your name still shows in the account drawer.
- Your name still shows on the chat speaker label.

## Optional

Skippable error and skip cases — run only if you want extra confidence.

### E1 — Get Started blocked on empty name (Personal app)
Arrange:
- A fresh, empty profile so the Welcome screen appears, with the First name field left blank.
Act:
- Leave the First name field empty and try to click Get Started.
Assert:
- The Welcome screen does not advance — you stay on it.
- A required-name indication appears, or the Get Started button is not active.

### E2 — Skip the wizard and use the app (Personal app)
Arrange:
- A fresh, empty profile so the Welcome screen appears.
Act:
- Click Skip for now, use the app briefly, then fully quit and re-open the Personal app.
Assert:
- The Welcome screen goes away and the chat and hamburger menu are present and usable.
- After re-opening, the Welcome screen does not reappear.
