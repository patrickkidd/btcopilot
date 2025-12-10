"""
Conversation Simulator

Orchestrates simulated conversations between the chatbot and synthetic users.
Runs a loop alternating between the real chatbot's ask() function and
LLM-generated user responses.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Callable

from btcopilot.extensions import db
from btcopilot.personal import ask as chatbot_ask
from btcopilot.personal.models import Discussion
from btcopilot.schema import PDP

from .personas import Persona

_log = logging.getLogger(__name__)


@dataclass
class Turn:
    """A single turn in a conversation."""

    role: str  # "user" or "assistant"
    content: str
    pdp: PDP | None = None  # PDP state after this turn (for assistant turns)


@dataclass
class SimulatedConversation:
    """Result of a simulated conversation."""

    persona: Persona
    turns: list[Turn] = field(default_factory=list)
    completed: bool = False
    completion_reason: str | None = None
    final_pdp: PDP | None = None

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def user_turns(self) -> list[Turn]:
        return [t for t in self.turns if t.role == "user"]

    @property
    def assistant_turns(self) -> list[Turn]:
        return [t for t in self.turns if t.role == "assistant"]

    def conversation_text(self) -> str:
        """Get full conversation as text."""
        lines = []
        for turn in self.turns:
            speaker = self.persona.name if turn.role == "user" else "Coach"
            lines.append(f"{speaker}: {turn.content}")
        return "\n".join(lines)


class ConversationSimulator:
    """
    Runs simulated conversations between the chatbot and synthetic users.

    Uses a cheap/fast LLM model for user simulation while the chatbot uses
    its production model.
    """

    def __init__(
        self,
        max_turns: int = 20,
        user_model: str = "gpt-4o-mini",
        completion_signals: list[str] | None = None,
    ):
        """
        Initialize the simulator.

        Args:
            max_turns: Maximum number of exchange pairs before stopping
            user_model: Model to use for synthetic user responses
            completion_signals: Phrases that signal conversation completion
        """
        self.max_turns = max_turns
        self.user_model = user_model
        self.completion_signals = completion_signals or [
            "I think we've covered everything",
            "That's all the family information",
            "END_CONVERSATION",  # Explicit signal for testing
        ]

    def _generate_user_response(
        self,
        persona: Persona,
        conversation_history: str,
        last_assistant_message: str,
    ) -> str:
        """Generate a synthetic user response using LLM."""
        import openai

        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        prompt = f"""You are playing the role of {persona.name} in a conversation with
a family systems coach. Stay in character.

{persona.system_prompt}

The conversation so far:
{conversation_history}

The coach just said: "{last_assistant_message}"

Respond as {persona.name} would. Stay in character. Keep your response realistic
and conversational (1-4 sentences typical). Do NOT break character or reference
that this is a simulation.

If you feel the coach has gathered enough information about your family situation
(names, ages, relationships, major events for 3 generations), you can naturally
wind down the conversation by saying something like "I think that covers most of
my family" or similar."""

        response = client.chat.completions.create(
            model=self.user_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )

        return response.choices[0].message.content.strip()

    def _generate_opening_message(self, persona: Persona) -> str:
        """Generate the synthetic user's opening message."""
        import openai

        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        prompt = f"""You are playing the role of {persona.name} starting a conversation
with a family systems coach. Stay in character.

{persona.system_prompt}

Generate an opening message that {persona.name} would say when first meeting with
a coach. This might be about why you're seeking help, or responding to a greeting.
Keep it realistic (1-3 sentences).

Do NOT break character or reference that this is a simulation."""

        response = client.chat.completions.create(
            model=self.user_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150,
        )

        return response.choices[0].message.content.strip()

    def _check_completion(self, user_response: str) -> tuple[bool, str | None]:
        """Check if the conversation should end."""
        user_lower = user_response.lower()

        for signal in self.completion_signals:
            if signal.lower() in user_lower:
                return True, f"Completion signal detected: {signal}"

        return False, None

    def run(
        self,
        persona: Persona,
        discussion: Discussion,
        opening_message: str | None = None,
    ) -> SimulatedConversation:
        """
        Run a simulated conversation.

        Args:
            persona: The synthetic user persona
            discussion: A Discussion object for the conversation
            opening_message: Optional custom opening (otherwise generated)

        Returns:
            SimulatedConversation with full history and results
        """
        result = SimulatedConversation(persona=persona)

        # Generate or use provided opening message
        if opening_message:
            user_message = opening_message
        else:
            user_message = self._generate_opening_message(persona)

        _log.info(f"Starting conversation with persona '{persona.id}'")
        _log.debug(f"Opening: {user_message}")

        for turn_num in range(self.max_turns):
            _log.debug(f"Turn {turn_num + 1}/{self.max_turns}")

            # Record user turn
            result.turns.append(Turn(role="user", content=user_message))

            # Get chatbot response
            try:
                response = chatbot_ask(discussion, user_message)
                db.session.commit()
            except Exception as e:
                _log.error(f"Chatbot error: {e}")
                result.completed = False
                result.completion_reason = f"Chatbot error: {e}"
                return result

            assistant_message = response.statement
            result.turns.append(
                Turn(role="assistant", content=assistant_message, pdp=response.pdp)
            )
            result.final_pdp = response.pdp

            _log.debug(f"Coach: {assistant_message}")

            # Check if we've hit the turn limit
            if turn_num >= self.max_turns - 1:
                result.completed = True
                result.completion_reason = "Max turns reached"
                _log.info(f"Conversation ended: max turns ({self.max_turns})")
                return result

            # Build conversation history for user response generation
            conversation_history = result.conversation_text()

            # Generate next user message
            user_message = self._generate_user_response(
                persona, conversation_history, assistant_message
            )
            _log.debug(f"{persona.name}: {user_message}")

            # Check for completion
            should_end, reason = self._check_completion(user_message)
            if should_end:
                result.turns.append(Turn(role="user", content=user_message))
                result.completed = True
                result.completion_reason = reason
                _log.info(f"Conversation ended: {reason}")
                return result

        result.completed = True
        result.completion_reason = "Max turns reached"
        return result

    def run_batch(
        self,
        personas: list[Persona],
        discussion_factory: Callable[[], Discussion],
        conversations_per_persona: int = 1,
        opening_messages: dict[str, str] | None = None,
    ) -> list[SimulatedConversation]:
        """
        Run multiple simulated conversations.

        Args:
            personas: List of personas to simulate
            discussion_factory: Callable that creates fresh Discussion objects
            conversations_per_persona: How many conversations to run per persona
            opening_messages: Optional dict of persona_id -> opening message

        Returns:
            List of SimulatedConversation results
        """
        results = []
        opening_messages = opening_messages or {}

        for persona in personas:
            for i in range(conversations_per_persona):
                _log.info(
                    f"Running conversation {i + 1}/{conversations_per_persona} "
                    f"for persona '{persona.id}'"
                )

                discussion = discussion_factory()
                opening = opening_messages.get(persona.id)

                result = self.run(persona, discussion, opening_message=opening)
                results.append(result)

        return results
