"""
Quality Evaluation Framework

Automated checks for detecting robotic patterns in chatbot responses:
- Repetitive phrases
- Verbatim echoing
- Excessive questioning
- Banned phrases
- Response variety metrics
"""

import re
import os
import logging
from dataclasses import dataclass, field
from collections import Counter
from difflib import SequenceMatcher

from .simulator import SimulatedConversation, Turn

_log = logging.getLogger(__name__)


@dataclass
class PatternViolation:
    """A detected pattern violation."""

    pattern_name: str
    description: str
    severity: str  # "warning", "error"
    turn_index: int | None = None
    content: str | None = None


@dataclass
class QualityScore:
    """Quality evaluation results for a conversation."""

    conversation_id: str | None = None
    persona_id: str | None = None

    # Scores (0.0 = bad, 1.0 = good)
    repetition_score: float = 1.0
    echo_score: float = 1.0
    variety_score: float = 1.0
    banned_phrase_score: float = 1.0
    question_balance_score: float = 1.0

    # Overall score (weighted average)
    overall_score: float = 1.0

    # Violations found
    violations: list[PatternViolation] = field(default_factory=list)

    # Metadata
    turn_count: int = 0
    assistant_turn_count: int = 0

    def passed(self, threshold: float = 0.7) -> bool:
        """Check if the conversation passes quality threshold."""
        return self.overall_score >= threshold

    def summary(self) -> str:
        """Get a human-readable summary."""
        status = "PASSED" if self.passed() else "FAILED"
        lines = [
            f"Quality Score: {self.overall_score:.2f} ({status})",
            f"  Repetition: {self.repetition_score:.2f}",
            f"  Echo avoidance: {self.echo_score:.2f}",
            f"  Variety: {self.variety_score:.2f}",
            f"  Banned phrases: {self.banned_phrase_score:.2f}",
            f"  Question balance: {self.question_balance_score:.2f}",
        ]
        if self.violations:
            lines.append(f"  Violations: {len(self.violations)}")
            for v in self.violations[:5]:  # Show first 5
                lines.append(f"    - [{v.severity}] {v.pattern_name}: {v.description}")
        return "\n".join(lines)


class RoboticPatternChecker:
    """Checks for specific robotic patterns in responses."""

    # Phrases that indicate robotic, therapist-speak responses
    BANNED_PHRASES = [
        "it sounds like",
        "that sounds",
        "it makes sense that",
        "that must be",
        "how does that make you feel",
        "tell me more",
        "i hear you",
        "i understand that",
        "thank you for sharing",
        "i appreciate you sharing",
        "that's really",
        "it's understandable",
    ]

    # Phrases that are okay in moderation but bad if overused
    MODERATION_PHRASES = [
        "i see",
        "okay",
        "got it",
        "i understand",
    ]

    def __init__(
        self,
        banned_phrases: list[str] | None = None,
        repetition_threshold: int = 2,
        echo_similarity_threshold: float = 0.6,
    ):
        """
        Initialize the pattern checker.

        Args:
            banned_phrases: Additional banned phrases to check
            repetition_threshold: Max times a phrase can repeat before flagging
            echo_similarity_threshold: Similarity ratio above which echoing is flagged
        """
        self.banned_phrases = self.BANNED_PHRASES.copy()
        if banned_phrases:
            self.banned_phrases.extend(banned_phrases)
        self.repetition_threshold = repetition_threshold
        self.echo_similarity_threshold = echo_similarity_threshold

    def check_banned_phrases(self, response: str) -> list[PatternViolation]:
        """Check for banned therapist-speak phrases."""
        violations = []
        response_lower = response.lower()

        for phrase in self.banned_phrases:
            if phrase in response_lower:
                violations.append(
                    PatternViolation(
                        pattern_name="banned_phrase",
                        description=f"Used banned phrase: '{phrase}'",
                        severity="warning",
                        content=phrase,
                    )
                )

        return violations

    def check_repetition(
        self, responses: list[str]
    ) -> tuple[list[PatternViolation], float]:
        """
        Check for repetitive phrases across responses.

        Returns violations and a score (1.0 = no repetition, 0.0 = severe repetition).
        """
        violations = []

        # Extract n-grams (phrases of 3-6 words)
        all_ngrams = []
        for response in responses:
            words = response.lower().split()
            for n in range(3, 7):
                for i in range(len(words) - n + 1):
                    ngram = " ".join(words[i : i + n])
                    all_ngrams.append(ngram)

        # Count occurrences
        ngram_counts = Counter(all_ngrams)

        # Find repeated phrases
        repeated = {
            phrase: count
            for phrase, count in ngram_counts.items()
            if count > self.repetition_threshold
        }

        for phrase, count in repeated.items():
            violations.append(
                PatternViolation(
                    pattern_name="repetition",
                    description=f"Phrase repeated {count} times: '{phrase}'",
                    severity="warning" if count <= 3 else "error",
                    content=phrase,
                )
            )

        # Calculate score
        if not responses:
            return violations, 1.0

        # Score based on unique phrase ratio
        total_ngrams = len(all_ngrams)
        unique_ngrams = len(set(all_ngrams))
        if total_ngrams == 0:
            score = 1.0
        else:
            score = unique_ngrams / total_ngrams

        return violations, score

    def check_echoing(
        self, user_message: str, assistant_response: str
    ) -> list[PatternViolation]:
        """Check if the assistant is parroting back what the user said."""
        violations = []

        # Check for direct echoing of user phrases
        user_sentences = re.split(r"[.!?]", user_message.lower())
        response_sentences = re.split(r"[.!?]", assistant_response.lower())

        for user_sent in user_sentences:
            user_sent = user_sent.strip()
            if len(user_sent) < 10:  # Skip very short phrases
                continue

            for resp_sent in response_sentences:
                resp_sent = resp_sent.strip()
                if len(resp_sent) < 10:
                    continue

                similarity = SequenceMatcher(None, user_sent, resp_sent).ratio()
                if similarity > self.echo_similarity_threshold:
                    violations.append(
                        PatternViolation(
                            pattern_name="echoing",
                            description=f"Response echoes user statement (similarity: {similarity:.2f})",
                            severity="warning",
                            content=f"User: '{user_sent[:50]}...' -> Response: '{resp_sent[:50]}...'",
                        )
                    )

        return violations

    def check_question_balance(
        self, responses: list[str]
    ) -> tuple[list[PatternViolation], float]:
        """
        Check if the chatbot is asking too many questions per response.

        Returns violations and a score.
        """
        violations = []
        question_counts = []

        for i, response in enumerate(responses):
            questions = response.count("?")
            question_counts.append(questions)

            if questions > 3:
                violations.append(
                    PatternViolation(
                        pattern_name="excessive_questions",
                        description=f"Response has {questions} questions (max recommended: 2-3)",
                        severity="warning",
                        turn_index=i,
                        content=response[:100] + "...",
                    )
                )

        # Score: penalize for too many questions
        if not question_counts:
            return violations, 1.0

        avg_questions = sum(question_counts) / len(question_counts)
        # Ideal: 1-2 questions per response
        if avg_questions <= 2:
            score = 1.0
        elif avg_questions <= 3:
            score = 0.8
        else:
            score = max(0.4, 1.0 - (avg_questions - 2) * 0.2)

        return violations, score

    def check_variety(self, responses: list[str]) -> tuple[list[PatternViolation], float]:
        """
        Check for response variety in openings and structure.

        Returns violations and a score.
        """
        violations = []

        if len(responses) < 3:
            return violations, 1.0

        # Check opening words
        openings = []
        for response in responses:
            words = response.split()
            if words:
                openings.append(words[0].lower())

        opening_counts = Counter(openings)
        most_common_opening, count = opening_counts.most_common(1)[0]

        if count > len(responses) * 0.5:  # Same opening in >50% of responses
            violations.append(
                PatternViolation(
                    pattern_name="repetitive_openings",
                    description=f"'{most_common_opening}' used to start {count}/{len(responses)} responses",
                    severity="warning",
                    content=most_common_opening,
                )
            )

        # Score based on opening variety
        unique_openings = len(set(openings))
        score = min(1.0, unique_openings / (len(responses) * 0.7))

        return violations, score


class QualityEvaluator:
    """
    Evaluates overall conversation quality.

    Combines multiple pattern checkers and optional LLM-based evaluation.
    """

    def __init__(
        self,
        pattern_checker: RoboticPatternChecker | None = None,
        use_llm_judge: bool = False,
        llm_model: str = "gpt-4o-mini",
    ):
        """
        Initialize the evaluator.

        Args:
            pattern_checker: Custom pattern checker (uses default if None)
            use_llm_judge: Whether to use LLM for additional naturalness scoring
            llm_model: Model to use for LLM judging
        """
        self.pattern_checker = pattern_checker or RoboticPatternChecker()
        self.use_llm_judge = use_llm_judge
        self.llm_model = llm_model

    def evaluate(self, conversation: SimulatedConversation) -> QualityScore:
        """
        Evaluate a simulated conversation.

        Args:
            conversation: The conversation to evaluate

        Returns:
            QualityScore with detailed metrics
        """
        score = QualityScore(
            persona_id=conversation.persona.id,
            turn_count=conversation.turn_count,
            assistant_turn_count=len(conversation.assistant_turns),
        )

        assistant_responses = [t.content for t in conversation.assistant_turns]

        # Check banned phrases
        banned_violations = []
        for i, response in enumerate(assistant_responses):
            violations = self.pattern_checker.check_banned_phrases(response)
            for v in violations:
                v.turn_index = i
            banned_violations.extend(violations)

        score.violations.extend(banned_violations)
        score.banned_phrase_score = max(0.0, 1.0 - len(banned_violations) * 0.1)

        # Check repetition
        rep_violations, rep_score = self.pattern_checker.check_repetition(
            assistant_responses
        )
        score.violations.extend(rep_violations)
        score.repetition_score = rep_score

        # Check echoing
        echo_violations = []
        for i, (user_turn, asst_turn) in enumerate(
            zip(conversation.user_turns, conversation.assistant_turns)
        ):
            violations = self.pattern_checker.check_echoing(
                user_turn.content, asst_turn.content
            )
            for v in violations:
                v.turn_index = i
            echo_violations.extend(violations)

        score.violations.extend(echo_violations)
        assistant_count = len(conversation.assistant_turns)
        if assistant_count > 0:
            score.echo_score = max(
                0.0, 1.0 - len(echo_violations) / assistant_count
            )
        else:
            score.echo_score = 1.0

        # Check question balance
        q_violations, q_score = self.pattern_checker.check_question_balance(
            assistant_responses
        )
        score.violations.extend(q_violations)
        score.question_balance_score = q_score

        # Check variety
        v_violations, v_score = self.pattern_checker.check_variety(assistant_responses)
        score.violations.extend(v_violations)
        score.variety_score = v_score

        # Optional LLM judge
        if self.use_llm_judge and conversation.turn_count > 2:
            llm_score = self._llm_judge(conversation)
            # Blend LLM score with rule-based scores
            rule_score = (
                score.repetition_score * 0.2
                + score.echo_score * 0.2
                + score.variety_score * 0.2
                + score.banned_phrase_score * 0.2
                + score.question_balance_score * 0.2
            )
            score.overall_score = rule_score * 0.6 + llm_score * 0.4
        else:
            # Weighted average of component scores
            score.overall_score = (
                score.repetition_score * 0.2
                + score.echo_score * 0.25
                + score.variety_score * 0.15
                + score.banned_phrase_score * 0.25
                + score.question_balance_score * 0.15
            )

        return score

    def _llm_judge(self, conversation: SimulatedConversation) -> float:
        """Use LLM to evaluate naturalness of the conversation."""
        import openai

        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        prompt = f"""You are evaluating the quality of a chatbot acting as a family systems coach.
Rate the COACH's responses (not the user's) on a scale of 0-10 for naturalness and
conversational quality.

Consider:
1. Does the coach sound natural or robotic/formulaic?
2. Does the coach avoid parroting back what the user said?
3. Does the coach ask relevant, specific questions vs. vague prompts?
4. Does the coach vary their response style or repeat the same patterns?
5. Does the coach avoid therapy cliches like "that sounds hard" or "tell me more"?

The conversation:
{conversation.conversation_text()}

Respond with ONLY a number from 0-10 (can be decimal like 7.5).
0 = completely robotic/unnatural
10 = perfectly natural and engaging"""

        try:
            response = client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=10,
            )
            score_text = response.choices[0].message.content.strip()
            score = float(score_text) / 10.0  # Normalize to 0-1
            return max(0.0, min(1.0, score))
        except Exception as e:
            _log.warning(f"LLM judge failed: {e}")
            return 0.5  # Neutral score on failure


def evaluate_conversation(
    conversation: SimulatedConversation,
    use_llm_judge: bool = False,
) -> QualityScore:
    """
    Convenience function to evaluate a conversation.

    Args:
        conversation: The conversation to evaluate
        use_llm_judge: Whether to use LLM for additional scoring

    Returns:
        QualityScore with detailed metrics
    """
    evaluator = QualityEvaluator(use_llm_judge=use_llm_judge)
    return evaluator.evaluate(conversation)
