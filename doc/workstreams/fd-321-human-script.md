# FD-321 Human Walkthrough: Welcome Setup & Profile (cross-app)

This walk uses TWO apps sharing ONE sandbox backend (the same server, same logged-in user): the **Personal app** and the **Pro app**. The Personal app owns the first-launch wizard, the Settings "Profile" editor, the chat/discussion speaker label, and the account drawer (hamburger menu) — but it does NOT render the family-diagram canvas, so you cannot see the diagram node there. The **Pro app**, opened against the SAME backend as the same user, is the ONLY place you SEE the diagram node with the name. The Pro app loads the server's current version when you open the diagram and does NOT live-sync another app's concurrent edit, so after saving in the Personal app you must (re-)open the free diagram in the Pro app to see the change — if the Pro app already had it open, close it and open it again.

The bet you are judging — the **identity spine (cross-app)**: a person's identity, captured ONCE in the Personal-app wizard, is consistent on the Pro-rendered diagram node, the Personal chat speaker label, and the account drawer. If this holds, later Personal-app work can safely treat "the diagram node = the account holder" without rework.

**Go / No-go judgment (yours alone):** the Welcome setup and Settings Profile flow look and feel right, and correctly describe YOU on YOUR real diagram across both apps. The machine already confirmed every mechanical behavior; you are judging the holistic feel and that the name describing the user is actually you, everywhere.

## Main path

### A1 — First launch shows Welcome (Personal app)
Arrange:
- Start from a brand-new, empty profile (no diagram set up yet) on the shared backend.
Act:
- Launch the Personal app.
Assert:
- A single "Welcome" setup screen appears on first launch.
- It shows two name fields (First name, Last name) and a birth date field.
- A "Get Started" button and a "Skip for now" link are both visible.

### A2 — Enter your name and check tab order (Personal app)
Arrange:
- The Welcome screen is showing with the First name field empty.
Act:
- Click the First name field, type your real first name, press Tab, type your real last name, press Tab.
Assert:
- Pressing Tab moved the cursor First name then Last name then birth date in that order.
- Your first and last name appear correctly in their fields.
- Focus is now on the birth date field.

### A3 — Set your birth date with the date control (Personal app)
Arrange:
- Focus is on the birth date field with your name already entered.
Act:
- Click the birth date field to expand the date picker, then set your real birth date (click or type it).
Assert:
- The birth date field expands into the same date picker used elsewhere in the app.
- Your chosen birth date shows in the field after you set it.

### A4 — Finish setup (Personal app)
Arrange:
- Your first name, last name, and birth date are all filled in.
Act:
- Click "Get Started".
Assert:
- The Welcome screen closes and the main Personal-app view appears.
- The chat/discussion screen and the hamburger menu are present and usable.

### A5 — See your node on the diagram (Pro app)
Arrange:
- You have finished setup in the Personal app. The Pro app is logged in as the same user against the same shared backend.
Act:
- In the Pro app, open the free diagram (if it was already open from before, close it and open it again so it loads the server's current version).
Assert:
- Your own node appears on the diagram with your name (no longer blank or "Client").
- The diagram reflects your birth date on your node.

### A6 — The spine: same name across both apps
Arrange:
- The diagram is open in the Pro app showing your node.
Act:
- In the Personal app, open the chat/discussion and read the speaker label next to your messages, then open the hamburger menu (top-left) to reveal the account drawer.
Assert:
- The diagram node (Pro app) shows your name.
- The chat speaker label (Personal app) shows YOUR name next to your messages, not "Client".
- The account drawer (Personal app) shows your name.
- The name on the Pro-app diagram node, the Personal-app chat label, and the account drawer are the SAME name.

### A7 — Edit name in Settings Profile (Personal app)
Arrange:
- The account drawer is open in the Personal app and showing your name.
Act:
- Open the "Profile" editor from the account drawer entry, confirm it is pre-filled with your current name, change the name (e.g. fix a spelling), and Save.
Assert:
- The Profile editor opened pre-filled with your current first and last name.
- After saving, the Personal app account drawer shows the updated name.
- The Personal app chat speaker label shows the updated name.
- Re-opening the free diagram in the Pro app (close it and open it again) shows the updated name on your node.

### A8 — Persistence across a real relaunch (Personal app)
Arrange:
- You have finished setup and your name is set.
Act:
- Fully quit the Personal app, then re-open (restart) it.
Assert:
- After re-opening, the Welcome setup screen does NOT reappear.
- Your name still shows in the account drawer.
- Your name still shows on the chat speaker label.

## Optional

Error and skip cases — skippable; run only if you want extra confidence.

### E1 — Get Started blocked with empty name (Personal app)
Arrange:
- A fresh, empty profile so the Welcome screen appears, with the First name field empty.
Act:
- Leave the First name field blank and try to click "Get Started".
Assert:
- The "Get Started" button stays disabled, or the screen indicates a name is required.
- You are not advanced past the Welcome screen.

### E2 — Skip the wizard and use the app (Personal app)
Arrange:
- A fresh, empty profile so the Welcome screen appears.
Act:
- Click "Skip for now".
Assert:
- The Welcome screen closes and the Personal app is fully usable (chat and hamburger menu are reachable).
- On the next launch the Welcome screen does NOT reappear.
