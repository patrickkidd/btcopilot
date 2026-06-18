# FD-321 Human Walkthrough: Welcome Setup & Profile (Personal app)

The bet you are judging — the **identity spine**: you tell the app who you are ONCE in the Welcome setup, and that single answer flows to and stays consistent across every place that names you — your own node on the diagram, the speaker label in chat, and the account drawer — with the account auto-synced on your own diagram. If this holds, later Personal-app work can safely treat "your node on the diagram = the account holder" without rework.

**Go / No-go judgment (yours alone):** the Welcome setup and Settings Profile flow look and feel right, and correctly describe YOU on YOUR real diagram. The machine already confirmed every mechanical behavior; you are judging the holistic feel and that the name describing the user is actually you, everywhere.

## Main path

### A1 — First launch shows Welcome
Arrange:
- Start from a brand-new, empty profile (no diagram set up yet).
Act:
- Launch the Personal app.
Assert:
- A single "Welcome" setup screen appears on first launch.
- It shows two name fields (First name, Last name) and a birth date field.
- A "Get Started" button and a "Skip for now" link are both visible.

### A2 — Enter your name and check tab order
Arrange:
- The Welcome screen is showing with the First name field empty.
Act:
- Click the First name field, type your real first name, press Tab, type your real last name, press Tab.
Assert:
- Pressing Tab moved the cursor First name then Last name then birth date in that order.
- Your first and last name appear correctly in their fields.
- Focus is now on the birth date field.

### A3 — Set your birth date with the date control
Arrange:
- Focus is on the birth date field with your name already entered.
Act:
- Click the birth date field to expand the date picker, then set your real birth date (click or type it).
Assert:
- The birth date field expands into the same date picker used elsewhere in the app.
- Your chosen birth date shows in the field after you set it.

### A4 — Finish setup
Arrange:
- Your first name, last name, and birth date are all filled in.
Act:
- Click "Get Started".
Assert:
- The Welcome screen closes and your diagram appears.
- Your name appears on your own node on the diagram (no longer blank or "Client").

### A5 — The spine: same name in all three surfaces
Arrange:
- Your diagram is showing after finishing setup.
Act:
- Open the chat/discussion and read the speaker label next to your messages, then open the hamburger menu (top-left) to reveal the account drawer.
Assert:
- The chat shows YOUR name next to your messages (not "Client").
- The account drawer shows your name.
- The name on the diagram node, the chat label, and the account drawer are the SAME name.

### A6 — Edit name in Settings Profile
Arrange:
- The account drawer is open and showing your name.
Act:
- Open the "Profile" editor from the account drawer entry, confirm it is pre-filled with your current name, change the name (e.g. fix a spelling), and save.
Assert:
- The Profile editor opened pre-filled with your current first and last name.
- After saving, the account drawer shows the updated name.
- Your node on the diagram shows the updated name (account and diagram stay in sync).

### A7 — Persistence across a real relaunch
Arrange:
- You have finished setup and your name is set.
Act:
- Fully quit the Personal app, then re-open (restart) it.
Assert:
- After re-opening, the Welcome setup screen does NOT reappear.
- Your name still shows on your diagram node.
- The account drawer still shows your name.

## Optional

Error and skip cases — skippable; run only if you want extra confidence.

### E1 — Get Started blocked with empty name
Arrange:
- A fresh, empty profile so the Welcome screen appears, with the First name field empty.
Act:
- Leave the First name field blank and try to click "Get Started".
Assert:
- The "Get Started" button stays disabled, or the screen indicates a name is required.
- You are not advanced past the Welcome screen.

### E2 — Skip the wizard and use the app
Arrange:
- A fresh, empty profile so the Welcome screen appears.
Act:
- Click "Skip for now".
Assert:
- The Welcome screen closes and the app is fully usable (you can open and work with the diagram).
- On the next launch the Welcome screen does NOT reappear.
