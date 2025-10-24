"""
CLI UI for the therapist module.
"""

import sys
import logging

from sqlalchemy import select, desc

from btcopilot.app import create_app
from btcopilot.extensions import db, ai_log
from btcopilot.pro.models import User
from btcopilot.personal import ask
from btcopilot.personal.models import Discussion, Speaker
from btcopilot.personal.prompts import BOWEN_THEORY_COACHING_IN_A_NUTSHELL

_log = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO, filename="debug_log.txt")
logging.getLogger("httpx").setLevel(logging.WARNING)

app = create_app()

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--restore", action="store_true")
options = parser.parse_args()


with app.app_context():

    user = User.query.get(1)

    if options.restore:
        discussion = db.session.scalars(
            select(Discussion)
            .where(Discussion.user_id == user.id)
            .order_by(desc(Discussion.id))
        ).first()
        if not discussion:
            _log.info("No discussion to restore.")
            sys.exit(1)
        _log.info(f"Discussion {discussion.id} restored")
        print(f"Discussion {discussion.id} restored")

        # prompt = f"""

        # You are a coach/consultant on helping people understand how the overhead
        # of anxiety/reactivity in relationships gets in the way of them meeting
        # their goals.

        # **Method and Expertise**

        # {BOWEN_THEORY_COACHING_IN_A_NUTSHELL}

        # **Instructions**

        # Generate a concise summary of what the user talked about in the
        # following conversation:

        # {discussion.conversation_history()}
        # """

        # results = gather(llm.submit(LLMFunction.Summarize, prompt, temperature=0.2))
        # print(results[0])

        print(f"Conversation summary: {discussion.summary}")

        last_ai_statement = discussion.statements[-1] if discussion.statements else None
        if last_ai_statement and last_ai_statement.speaker.type == Speaker.Expert:
            print("\nLast AI statement:")
            print(last_ai_statement.text)
    else:
        discussion = Discussion(user_id=user.id)
        db.session.add(discussion)
        db.session.commit()
        ai_log.info("New discussion created")
        print("\n\nDiscussion created")

    num_statements = 0
    while True:
        try:
            statement = input("You: ".ljust(8))
        except KeyboardInterrupt:
            break
        response = ask(discussion, statement)
        print("AI: ".ljust(8) + response.statement)

        # Update the summary every 2 statements
        num_statements += 1
        if num_statements % 2 == 0:
            discussion.update_summary()
            ai_log.info(f"Discussion {discussion.id} summary updated")

        db.session.commit()
