# Psychological Foundations for Synthetic Client Persona Generation

**Purpose**: Documents the empirical research basis for how synthetic client personas are constructed and evaluated in the Family Diagram conversation system. Written for clinicians and researchers familiar with personality psychology, attachment theory, and clinical assessment.

**Related**: [SYNTHETIC_CLIENT_PROMPT_SPEC.md](SYNTHETIC_CLIENT_PROMPT_SPEC.md) (implementation spec) | [Implementation Plan](../plans/SYNTHETIC_CLIENT_PERSONALITIES.md)

---

## Overview

The synthetic client system generates AI personas that simulate first-session clinical interviews for training and evaluation purposes. Rather than using ad hoc behavioral labels (e.g., "evasive," "defensive"), persona construction is grounded in three empirically validated frameworks that predict distinct aspects of clinical communication:

1. **Attachment theory** — predicts narrative structure
2. **Big Five personality dimensions** — predicts conversational style and internal coherence
3. **Sex-differentiated and generational communication norms** — predicts presentation framing and vocabulary

Each framework operates at a different level of the conversational output. Attachment style shapes *how the story is structured*. Big Five dimensions shape *how the person communicates*. Sex and generational norms shape *how the person frames their distress*.

---

## 1. Attachment Theory and Narrative Structure

### Theoretical Basis

The Adult Attachment Interview (AAI; George, Kaplan, & Main, 1985) demonstrated that attachment classification can be derived not from the *content* of what adults report about childhood relationships, but from the *structural properties* of their narratives. The Main and Goldwyn (1998) coding system scores transcripts on dimensions including coherence, idealization, insistence on lack of memory, passivity of discourse, and unresolved/disorganized responses to loss or trauma.

This finding — that attachment is encoded in narrative structure rather than narrative content — is the central insight driving the persona generation system. An LLM can be prompted to produce narratives with specific structural properties corresponding to each attachment classification.

### Four Attachment Classifications and Their Narrative Signatures

**Secure/Autonomous (F)**

Coherent, collaborative discourse. The speaker can describe both positive and negative childhood experiences, integrating them into a balanced account. Emotional language is appropriate to content — neither affectively flat nor overwhelmed. The speaker is comfortable acknowledging uncertainty ("I'm not sure why she did that, but I think...") and can reflect on experiences without becoming absorbed in them.

*Clinical presentation*: Organized storytelling with appropriate affect. Can describe difficult events without either minimizing or flooding. Responds to the clinician's questions directly. May still have significant distress — secure attachment does not mean absence of problems — but processes it with relative coherence.

**Dismissing (Ds)**

Brief, often idealized accounts lacking episodic support. The speaker may describe parents as "great" or "normal" but cannot provide specific memories that substantiate these claims. Alternatively, derogates attachment relationships ("It didn't matter" / "I don't think about it"). Discourse violations include contradictions between semantic and episodic memory — claiming a relationship was fine while describing behavior that suggests otherwise.

*Clinical presentation*: Answers sound complete but are affectively empty. Talks readily about logistics, facts, and timelines but deflects emotional content. The clinician must notice what is *missing* rather than what is said. May present as high-functioning precisely because distress is not registered or reported.

**Preoccupied (E)**

Long, entangled, often incoherent accounts. The speaker becomes absorbed in past experiences, losing the collaborative frame of the interview. Past-tense violations are common (shifting from describing a childhood event to addressing the parent directly, as if they were present). Narratives are detailed but disorganized — the speaker may return to the same grievance repeatedly, often with fresh affect. Monitoring of discourse quality is poor.

*Clinical presentation*: Floods the clinician with information. Seeks reassurance ("Do you think that was normal?" / "Am I making sense?"). Difficulty completing a thought before starting the next. High emotional vocabulary but low emotional regulation within the narrative. May be hypervigilant to the clinician's reactions.

**Unresolved/Disorganized (U/d)**

Lapses in the monitoring of reasoning or discourse specifically when discussing loss or trauma. These lapses may include: speaking about a deceased person as if alive, long silences mid-sentence, sudden shifts in register or topic, disorientation in time or space within the narrative. Outside of loss/trauma topics, the transcript may appear organized (and receives a secondary best-fitting classification).

*Clinical presentation*: The most challenging presentation for clinicians. The narrative may appear organized until a specific topic triggers fragmentation. The person may begin to disclose and then abruptly shut down, or shift between seeking closeness and pushing away within a single exchange. This classification is currently the least represented in synthetic persona research and the most valuable for clinician training.

### Application to Persona Generation

Each generated persona is assigned an attachment classification that constrains the narrative structure instructions in the LLM prompt. The attachment style does not appear as a label in the conversation — it manifests through structural properties that the clinician (or evaluation rubric) must detect.

The evaluation framework (client rubric, `narrative_coherence` dimension) assesses whether the generated transcript exhibits structural properties consistent with the assigned attachment classification.

---

## 2. Big Five Personality Dimensions (OCEAN)

### Theoretical Basis

The Five-Factor Model (Costa & McCrae, 1992) is the most extensively replicated dimensional model of personality. Each factor predicts distinct patterns of behavior in clinical settings, though the FFM was not designed for clinical use. Its relevance here is as an *internal coherence constraint* — ensuring that the behavioral traits assigned to a synthetic persona form a psychologically plausible profile rather than an arbitrary combination.

### Dimension-to-Behavior Mappings in Clinical Conversation

**Neuroticism (N)**

High-N individuals exhibit rumination (returning to the same concern unprompted), catastrophizing, reassurance-seeking, and physiological arousal markers in speech (choppy, pressured delivery). Low-N individuals minimize distress, underreport symptoms, and may present as untroubled when clinical indicators suggest otherwise. The distinction between low-N and dismissing attachment is important: low-N reflects genuine low reactivity to negative affect, while dismissing attachment reflects motivated avoidance of attachment-related affect specifically.

**Agreeableness (A)**

High-A individuals accommodate the interviewer's framing, avoid disagreement, and may produce artificially coherent narratives by telling the clinician what they appear to want to hear. This is a validity threat in clinical assessment. Low-A individuals challenge the process, question interpretations, and push back on premises — behaviors often conflated with "defensiveness" but which may reflect skepticism rather than threat reactivity.

**Extraversion (E)**

High-E individuals fill silences, think aloud, narrate with dramatic emphasis, and may find the clinical encounter energizing. Low-E individuals require processing time, produce shorter but more deliberate responses, and may experience the encounter as draining. The distinction between low-E and behavioral terseness is clinically meaningful: a terse client may be fully willing to disclose but simply uses fewer words.

**Openness (O)**

High-O individuals generate metaphors spontaneously, wonder about patterns without prompting, and are comfortable with abstract connections across generations. Low-O individuals are concrete, literal, and pragmatic — "What does my grandmother have to do with my insomnia?" is a low-O response, not necessarily a defensive one. In a Bowen theory context, low-O clients may resist multigenerational exploration on epistemological grounds rather than emotional ones.

**Conscientiousness (C)**

High-C individuals provide dates, names, and chronological sequences with organizational structure. They may arrive having prepared what to say. Low-C individuals produce associative, temporally disorganized narratives and may need the clinician to help impose structure. This dimension is largely absent from existing behavioral trait systems but produces significant variation in clinical interview data.

### Application to Persona Generation

Big Five dimensions are not exposed as user-facing parameters. Instead, they serve as an internal design constraint: when the LLM generates a persona from a trait + attachment style combination, the generation prompt includes an approximate Big Five profile derived from the selected parameters to ensure behavioral coherence. For example, Defensive + Dismissive-Avoidant maps approximately to low-A, low-N — the generation should not produce a persona who is simultaneously defensive and emotionally volatile, as that would be internally inconsistent (the correct combination for defensive + emotionally volatile would be low-A, high-N, mapping to Fearful-Avoidant attachment).

---

## 3. Sex Differences in Clinical Communication

### Theoretical Basis

Population-level sex differences in clinical communication are well-documented across several domains relevant to clinical interview simulation. These are probabilistic defaults, not deterministic rules — individual variation is substantial, and deviations from population norms can themselves be clinically informative.

### Domains of Difference

**Help-Seeking and Problem Framing**

Men are significantly less likely to seek help voluntarily (Addis & Mahalik, 2003) and more likely to frame problems in situational or behavioral terms ("My wife and I have been arguing") rather than emotional terms ("I've been feeling overwhelmed"). This affects the presenting problem generation: a male persona's opening statement should default to behavioral/situational framing unless the trait profile suggests otherwise.

**Emotional Vocabulary**

Women tend to use more differentiated emotional language, distinguishing between related states (anxious vs. worried vs. nervous vs. on edge). Men tend toward global affective labels (stressed, off, not great) and are more likely to answer emotional questions with behavioral descriptions ("I just went back to work") rather than affective labels ("I felt helpless") (Barrett, Lane, Sechrest, & Schwartz, 2000). This calibrates the vocabulary used in synthetic client responses.

**Rapport-Talk vs. Report-Talk**

Tannen's (1990) distinction between connection-oriented and information-oriented discourse styles predicts how clients relate to the clinical encounter. Women are more likely to make bids for connection ("You probably see this all the time"), ask personal questions of the clinician, and respond to emotional tone. Men are more likely to treat the session as an information exchange ("What do you need to know?") and focus on problem-solving.

**Externalizing vs. Internalizing Presentation**

Men are more likely to frame distress as anger, frustration, or blame ("She's being unreasonable"). Women are more likely to frame it as anxiety, sadness, or self-blame ("I think I'm not handling this well"). This difference affects how defensiveness manifests — male defensiveness often presents as irritation, female defensiveness as deflection or minimizing (Rosenfield & Mouzon, 2013).

**Somatic Presentation**

Men are more likely to present with somatic complaints — headaches, sleep disruption, gastrointestinal symptoms, fatigue — rather than naming emotional states directly (Simon & VonKorff, 1991). A realistic male persona may lead with physical symptoms where the underlying issue is relational.

### Application to Persona Generation

The generation form includes sex as a parameter. The LLM generation prompt incorporates sex-differentiated defaults for presenting problem framing, emotional vocabulary, rapport orientation, and somatic presentation. A male persona who deviates from these defaults (e.g., high emotional vocabulary, therapy-acculturated) should have that deviation reflected as a character detail in the background (e.g., "Has been in therapy before" / "Grew up in a household where feelings were discussed openly").

---

## 4. Age and Generational Communication Norms

### Theoretical Basis

Age effects and cohort effects jointly influence clinical communication style. These are distinguishable: age effects reflect developmental changes in narrative style and emotional regulation, while cohort effects reflect the norms of the cultural era in which a person was socialized.

### Key Differences

**Younger Adults (20s-30s)**: More likely to use psychological vocabulary acquired through social media and popular culture ("boundaries," "trauma," "toxic," "gaslighting"). May have prior therapy experience or expectations shaped by influencer therapy culture. More likely to self-diagnose using pop psychology constructs. Expects collaborative, non-hierarchical clinical relationships.

**Older Adults (50s+)**: More extended narrative style — stories are longer and more contextual. Less likely to use clinical terminology. May view help-seeking as weakness or as appropriate only in crisis. Different expectations about clinician authority and appropriate self-disclosure with a professional stranger. A 55-year-old woman raised by Greatest Generation parents has fundamentally different defaults around self-disclosure than a 28-year-old man who grew up with therapy normalized on social media.

### Application to Persona Generation

Age range is a form parameter. The generation prompt includes age-appropriate communication norms that calibrate vocabulary, help-seeking framing, and relationship to the clinical process.

---

## 5. Integration: From Dimensions to Conversation

The key insight across all three frameworks is that personality determines *how someone structures their narrative* more than *what topics they approach or avoid*:

| Narrative Property | Primary Predictor |
|-------------------|-------------------|
| Coherent vs. fragmented | Attachment style |
| Emotionally differentiated vs. global | Sex differences, Neuroticism |
| Self-focused vs. other-focused | Agreeableness, sex differences |
| Organized vs. associative | Conscientiousness, Extraversion |
| Abstract vs. concrete | Openness |
| Somatic vs. affective framing | Sex differences, age/generation |

Surface behavioral labels (evasive, defensive, terse) are symptoms of these deeper dimensions. Generating personas from the dimensions up produces more internally consistent and clinically realistic conversations than mixing and matching behavioral labels.

---

## References

Addis, M. E., & Mahalik, J. R. (2003). Men, masculinity, and the contexts of help seeking. *American Psychologist, 58*(1), 5-14.

Barrett, L. F., Lane, R. D., Sechrest, L., & Schwartz, G. E. (2000). Sex differences in emotional awareness. *Personality and Social Psychology Bulletin, 26*(9), 1027-1035.

Costa, P. T., & McCrae, R. R. (1992). *Revised NEO Personality Inventory (NEO-PI-R) and NEO Five-Factor Inventory (NEO-FFI) professional manual.* Psychological Assessment Resources.

George, C., Kaplan, N., & Main, M. (1985). *Adult Attachment Interview.* Unpublished manuscript, University of California, Berkeley.

Main, M., & Goldwyn, R. (1998). *Adult attachment scoring and classification systems.* Unpublished manuscript, University of California, Berkeley.

Rosenfield, S., & Mouzon, D. (2013). Gender and mental health. In C. S. Aneshensel, J. C. Phelan, & A. Bierman (Eds.), *Handbook of the sociology of mental health* (pp. 277-296). Springer.

Simon, G. E., & VonKorff, M. (1991). Somatization and psychiatric disorder in the NIMH Epidemiologic Catchment Area study. *American Journal of Psychiatry, 148*(11), 1494-1500.

Tannen, D. (1990). *You just don't understand: Women and men in conversation.* Ballantine Books.
