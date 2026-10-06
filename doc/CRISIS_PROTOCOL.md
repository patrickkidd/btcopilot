# Crisis protocol

What the coach does when a person says they may want to end their life or harm themselves.
Written so it can be published on the website, as California's companion chatbot law
(Business and Professions Code section 22602(b)(2)) asks. Rulings: R-0790, R-0797.

## What starts it

Every message the person sends is checked against a fixed list of phrases, before the coach
answers. No model judges it. The check ignores capital letters and accepts a missing apostrophe
("cant" for "can't").

**Saying they want to die**: want to die; wish I was dead (or were dead); kill myself; end my
life; end it all; take my own life; suicidal; thinking about suicide or thoughts of suicide;
better off dead; better off without me; no reason to live or no point in living; can't go on;
don't want to be here any more or don't want to wake up.

**Harming themselves**: hurt myself; cut myself; harm myself or self-harm; burn myself;
punish myself.

**A plan or a means**: have a plan to die or to end it (or a plan said in the same message as one
of the phrases about wanting to die); saved up or stockpiling pills, or an overdose; a goodbye
note or a suicide note (or "wrote a note" in the same message as one of the phrases about wanting
to die); giving my things away; a gun, the bridge or jumping, in the same message as one of the
phrases about wanting to die; saying goodbye to everyone, or "this is goodbye".

**What does not start it**:

| What the person says | Why it does not start it |
|---|---|
| "My mother wanted to die", "my father said he'd kill himself" | It is about someone else: the nearest person before the phrase is not the person writing. |
| She wrote "I want to die" in her diary | Words inside quotation marks, or reported from someone else ("she said", "he told me", "she texted"), are not the person's own. |
| "I didn't hurt myself", "I would never kill myself" | A not, never, didn't, wouldn't or won't within three words before it cancels it. |
| "Dying to know", "this is killing me", "I could kill him", "kill myself laughing" | Only the fixed phrases count; the bare words die, dying, kill and dead never do. |
| "I want to end it with him", "end it all and start over at a new job" | "End it" alone never counts, nor "end it all" followed by with, at, or "and start over". |
| "My brother cut himself as a teenager" | Someone else, in the past. |
| "How do you know if someone is suicidal?" | A question about someone, a person or people. |
| "I cut myself off from my family" | Cutting oneself off from people is not harm. |

The person's own past still counts: "I was suicidal in college" starts the less explicit reply
once, since a past attempt raises present risk.

## What the coach says

Plain words, no exclamation marks, no advice beyond the crisis line, the person's own words said
back, one question that keeps them talking, and no question about dates, names or the family
record.

**When the statement is explicit**, for example "Honestly I just want to die.":

> You said you want to die, and I'm taking that seriously. You can call or text 988 at any hour
> and talk with a person there; it's free. I'm here too, so what's happening for you right now?

**When it is less explicit**, for example "I can't go on like this.", or told about the past, or
"punish myself", "saying goodbye to everyone", "this is goodbye":

> When you say you can't go on, I want to understand what you mean. If it ever means thinking
> about ending your life, you can call or text 988 at any hour and talk with a person there.
> What's it like for you right now?

**When a plan or a means is named**, one sentence comes before the line: "If you're in danger
right now, call 911." (the emergency number of the person's country).

**On the turns after**, until the person moves back to their family by themselves: the coach
stays with what they say and asks nothing about the record; it still keeps a fact they offer,
without asking about it; it gives the line again only when one of the phrases comes up again; it
never ends the conversation and never tells them what to do beyond the line; if they say they
are fine and move on, it follows them and does not come back to it, then or at a later sitting,
unless they do.

## The line for each country

The country comes from the time zone of the person's account (for example America/Toronto is
Canada, Europe/Dublin is Ireland). Every line is free and open at all hours.

| Country | What the coach says | Emergency |
|---|---|---|
| United States | call or text 988 | 911 |
| Canada | call or text 988 | 911 |
| United Kingdom | call Samaritans on 116 123 or text SHOUT to 85258 | 999 |
| Ireland | call Samaritans on 116 123 or text HELLO to 50808 | 112 or 999 |
| Australia | call Lifeline on 13 11 14 or text 0477 13 11 14 | 000 |
| New Zealand | call or text 1737 | 111 |
| Anywhere else, or no time zone | call or text 988 if you're in the US, or find the line where you are at findahelpline.com | 911 in the US, or your local emergency number |

## What is counted

The conversational-flow counts (`flask admin flow track`, written to files outside every
repository, with no message text) carry, per thread, model and prompt version: how many of the
person's messages started the protocol, split into the three groups above, and how many of the
coach's replies to them met it (named the line for the country, asked exactly one question, asked
no date or fact question, gave no advice).

## Deferred

A stored row for each message that starts the protocol, and its panel on the quality dashboard,
need a database change; they wait until database changes are allowed again after the early beta
(R-0797). Until then the counts above are the record, and the number California asks for each
year (crisis referral notices shown, from 1 July 2027) is not yet kept in the database.
