# Sridhar et al. 2021: The Geometry of Decision-Making in Individuals and Collectives

**Citation**: Sridhar, V.H., Li, L., Gorbonos, D., Nagy, M., Schell, B.R., Sorochkin, T., Gov, N.S., & Couzin, I.D. (2021). The geometry of decision-making in individuals and collectives. *PNAS*, 118(50), e2102157118.

**Source**: `/Users/patrick/Documents/6 - References/Biology and Systems/Collective Intelligence and Behavior/sridhar-et-al-2021-the-geometry-of-decision-making-in-individuals-and-collectives.pdf`

**Date Captured**: 2026-01-04
**Date Expanded**: 2026-01-04 (exhaustive re-read)

**Journal Classification**: ECOLOGY / BIOPHYSICS AND COMPUTATIONAL BIOLOGY

**Keywords from paper**: ring attractor | movement ecology | navigation | collective behavior | embodied choice

---

## Abstract (Verbatim)

"Choosing among spatially distributed options is a central challenge for animals, from deciding among alternative potential food sources or refuges to choosing with whom to associate. Using an integrated theoretical and experimental approach (employing immersive virtual reality), we consider the interplay between movement and vectorial integration during decision-making regarding two, or more, options in space. In computational models of this process, we reveal the occurrence of spontaneous and abrupt "critical" transitions (associated with specific geometrical relationships) whereby organisms spontaneously switch from averaging vectorial information among, to suddenly excluding one among, the remaining options. This bifurcation process repeats until only one option—the one ultimately selected—remains. Thus, we predict that the brain repeatedly breaks multichoice decisions into a series of binary decisions in space–time. Experiments with fruit flies, desert locusts, and larval zebrafish reveal that they exhibit these same bifurcations, demonstrating that across taxa and ecological contexts, there exist fundamental geometric principles that are essential to explain how, and why, animals move the way they do."

---

## Significance Statement (Verbatim)

"Almost all animals must make decisions on the move. Here, employing an approach that integrates theory and high-throughput experiments (using state-of-the-art virtual reality), we reveal that there exist fundamental geometrical principles that result from the inherent interplay between movement and organisms' internal representation of space. Specifically, we find that animals spontaneously reduce the world into a series of sequential binary decisions, a response that facilitates effective decision-making and is robust both to the number of options available and to context, such as whether options are static (e.g., refuges) or mobile (e.g., other animals). We present evidence that these same principles, hitherto overlooked, apply across scales of biological organization, from individual to collective decision-making."

---

## Core Thesis

**The brain repeatedly breaks multichoice decisions into a series of binary decisions in space-time.**

Animals moving toward multiple spatially distributed options exhibit spontaneous "critical" transitions (bifurcations) where they suddenly switch from **averaging** vectorial information among options to **excluding** one option. This process repeats until only one option remains.

This is not just about *which* option is chosen, but about **how organisms move through the decision-making process** — the geometry of the decision itself.

---

## Introduction: The Problem of Spatial Decision-Making

### What Prior Studies Focused On

Most studies have focused on:
1. **The outcome of decisions** — which option among alternatives is chosen (refs 1-3)
2. **The time taken** to make decisions (refs 4-6)

But **seldom** on the **movement of animals throughout the decision-making process**.

### Why Motion Matters

> "Motion is, however, crucial in terms of how space is represented by organisms during spatial decision-making."

The brains of a wide range of species, from insects (refs 7, 8) to vertebrates (refs 9, 10), represent **egocentric spatial relationships** via **explicit vectorial representation** (refs 11, 12).

Key insight about why movement matters:

> "While the movement of an animal may, initially, appear to simply be a readout of the decision made by the brain—and consequently, not particularly informative—this view overlooks important dynamical properties introduced into the decision-making process that result from the inevitable time-varying geometrical relationships between an organism and spatially distributed options (i.e., potential 'targets' in space)."

### Study Objective

> "Due to a dearth of existing studies and with the objective to develop the necessary foundational understanding of the 'geometry' of decision-making, we focus here—first theoretically and then experimentally—on the consequences of the recursive interplay between movement and (collective) vectorial integration in the brain during relatively simple spatial decisions."

---

## The Neural Decision-Making Model

### Theoretical Foundation

The model assumes organisms have an **egocentric vectorial representation of spatial options** (refs 11-13).

The model considers:
- **Reinforcement (excitation/positive feedback)** among neural ensembles with similar directional representations (goal vectors)
- **Global inhibition and/or negative feedback** among neural ensembles that differ in vectorial representation

This captures the essence of:
1. **Explicit ring attractor networks** (as found in insects, ref 7)
2. **Computation among competing neural groups** (as in the mammalian brain, ref 14)

### Key Model Properties

1. **Relative preference** for a target = activity of neurons encoding that target's direction relative to activity of neurons encoding other targets' directions

2. **Angular sensitivity** of neural representations (angular difference at which excitation no longer occurs) is specified by the **neural tuning parameter, ν**

3. The network computes a unique **"consensus" vector** ("activity bump") that represents the animal's desired direction of movement

4. **Stochasticity** in neural dynamics is implemented as the **neural noise parameter, T**

### Why a Minimal Model

The paper deliberately uses a minimal model for multiple reasons:

1. **Maximum parsimony** — find a simple model that can both predict and explain observed phenomena

2. **General principles** — consider features known to be valid across organisms irrespective of differences in structural brain organization

3. **Convenient neural noise implementation** — can be mapped to the class of neural ring attractor models widely used in neuroscience (refs 16-19)

4. **Robustness** — results are extremely robust to model assumptions, suggesting appropriate low-level description of essential system properties

### Mathematical Formulation

#### Architecture

- Brain = system of N **spins** (representing neural activity)
- Each spin i encodes direction to one of the presented goals p̂ᵢ
- Spins exist in one of two states: σᵢ = 0 or σᵢ = 1

**Important clarification**: "We do not imply that a spin is equivalent to a neuron but rather, as we show via a mathematical derivation, that the collective properties of interacting spins in our model are equivalent to the firing rate in the neural ring attractor model."

#### Hamiltonian (Energy Function)

```
H = -k/N Σ(i≠j) Jij σi σj
```

Where:
- k = number of options available to the individual
- Jᵢⱼ = interaction strength between spins i and j
- σᵢ = state of spin i (0 or 1)

#### Interaction Strength

```
Jij = cos(π × (|θij|/π)^ν)
```

Where:
- θᵢⱼ = angle between preferred directions of spins i and j
- ν = neural tuning parameter
  - ν = 1: "cosine-shaped" interactions, Jᵢⱼ = cos(θᵢⱼ), network has **Euclidean representation of space**
  - ν < 1: more local excitation, network encodes space in **non-Euclidean manner**

#### System Dynamics

- Implemented by **energy minimization** using the **Metropolis-Hastings algorithm** (similar to other Ising spin models)

#### Movement Equation

```
V = v₀/N Σ(i=1 to N) p̂ᵢ σᵢ
```

Where:
- V = velocity vector
- v₀ = proportionality constant
- p̂ᵢ = goal vector of spin i (points from agent's updated location to its preferred goal)
- Directional noise chosen from a **circularly wrapped Gaussian distribution** centered at zero with SD σₑ

#### Timescale Relationship

> "As in the mean-field approximation of the model, the timescale of movement (defined by the typical time to reach the target) in the numerical simulations was set to be much greater than the timescale of neural activity (the typical time between two consecutive changes in the neural states σᵢ)."

---

## Key Findings

### 1. Deciding Between Two Options

When an animal is presented with two equally attractive, but spatially discrete options:
- Activity of neurons encoding option 1 (N₁) equals those encoding option 2 (N₂)

**Model prediction**:
1. Animal moving from distant location toward targets will spontaneously compute the **average directional preference**
2. Results in motion **oriented between the two targets**
3. Upon reaching a **certain angular difference**, the internal network undergoes a **sudden transition**
4. Network **spontaneously selects one or the other target**
5. Results in **abrupt change in trajectory**: animal redirected toward selected target

**Critical insight (verbatim)**:

> "Our model, therefore, predicts that despite the fact that the egocentric geometrical relationship between the animal and the targets changes continuously, upon approaching the targets there exists a location whereby a further very small increase in angular difference between the targets will result in a sudden change in system (neural) dynamics and consequently, in motion and thus, decision-making."

**What doesn't explain this**:
- Simply integrating noisy vectorial information
- Choosing travel direction from a summed distribution of target locations (PDF sum-based models, ref 20)

**Numerical analysis finding**: Irrespective of starting position, as the animal reaches the respective angle in space, it will relatively suddenly select one of the options.

**Factors affecting the specific angle**:
- Dependent on neural tuning ν
- Dependent on starting configuration (due to interplay between two timescales involved)
- Always present as long as neural noise T remains below critical firing rate Tᵧ
- For T < Tᵧ, bifurcations may be difficult to see for small values of ν due to inherent noise in real biological systems

### 2. Geometric Principles and Phase Transitions

**Mean-field analysis finding**:

Below a critical level of neural noise, animals will:
1. Adopt the **average among options** as they approach targets
2. Until a **critical phase transition**
3. Upon which the system **spontaneously switches to deciding** among options

> "Thus, despite varying in its exact location, the sudden transition observed is an inevitable consequence of the system dynamics and will always occur."

**Mathematical nature**: These sudden transitions correspond to **"bifurcations"** in dynamical systems.

**Definition**: "A bifurcation is said to occur when a smooth change in an external parameter, in this case perceived angular difference between the options, causes a sudden qualitative change in the system's behavior, here corresponding to a literal bifurcation (or branching) in physical space."

**Universal property of phase transitions** (verbatim):

> "When dynamical systems undergo such a phase, or quasiphase, transition, they exhibit a remarkable universal property; close to the transition, at the 'critical point' or 'tipping point,' the system spontaneously becomes extremely sensitive to very small perturbations [e.g., to small differences in preference between options (refs 21, 22)]. This is true of both physical [e.g., magnetic (ref 23)] and biotic [e.g., cellular (refs 24, 25)] systems undergoing a phase transition."

**Model finding**: Below critical neural noise, the mean-field model exhibits a **sudden increase in susceptibility** as the animal approaches the critical point, immediately prior to the decision being made.

**Critical prediction** (verbatim):

> "Thus, as animals approach targets, we predict they will pass through a window of space (corresponding to the critical angle for the respective geometry they are experiencing) in which their brain spontaneously becomes capable of discriminating between very small differences between options (e.g., a very small difference in neuronal activity being in 'favor' of one option)."

**Key point**: "This highly valuable property (for decision-making) is not built into the model but is rather an emergent property of the inherent collective dynamics."

**Real biological systems caveat**:

> "In many real biological systems, including the ones we consider here, the (neural) system size is typically not large enough to consider true phase transitions (which only occur for very large systems, as per the mean-field approximation) but rather, 'phase transition–like' or 'quasiphase transition' behavior. Even though real biological systems are not necessarily close to the infinite size limit of the mean-field approximation, we see very similar dynamics for both small and large system sizes."

### 3. Decision-Making Beyond Two Options

**Important methodological note**: "Note that we do not modify our model in any way prior to introducing these additional complexities."

**Three-choice decision process** (below Tᵧ):

1. When relatively far from targets, animal moves in the **average of three directions**
2. Upon reaching **critical angular threshold between leftmost and rightmost options** (from animal's perspective), the neural system **spontaneously eliminates one** of them
3. Animal begins moving in the **direction average between the two remaining options**
4. Continues until a **second critical angle** is reached
5. Animal **eliminates one of two remaining options** and moves toward the only remaining target

**Core prediction** (verbatim):

> "Thus, we predict that the brain repeatedly breaks multichoice decisions into a series of binary decisions in space–time."

**What doesn't work**: "Such bifurcation dynamics are not captured in models of decision-making that do not include the required feedbacks, such as if individuals simply sum noisy vectors (or PDFs) to targets in their sensory field."

**Three-target failure mode of simple models**: "For the case of three targets, vectors/votes to the leftmost option would tend to cancel those that favor the rightmost option, resulting in the selection of the central option."

**Robustness demonstrated**: Simulating 4, 5, 6, and 7 options (Figure 2), and varying environmental geometries, demonstrates the robustness of this mechanism in the face of environmental complexity and the more complex spatial dynamics that emerge as organisms undergo repeated bifurcations.

---

## Experimental Validation

### Virtual Reality Methodology

Experiments used **immersive virtual reality** (ref 28) to test predictions.

### Organisms and Contexts

| Organism | Scientific Name | Decision Context | Sample Details |
|----------|----------------|------------------|----------------|
| Fruit flies | *Drosophila melanogaster* | Choosing which pillar to approach/perch | 3-5 day old female wild-type canton special (CS) strain, raised at 26°C on 12h light/dark cycle, 60 tethered flies (30 each for 2-choice and 3-choice) |
| Desert locusts | *Schistocerca gregaria* | Choosing which pillar to approach | Instar 5, 156 total (57 for 2-choice, 99 for 3-choice), 122 used after filtering |
| Larval zebrafish | *Danio rerio* | Choosing which conspecific to school with | 1 ± 0.1 cm long, age 24-26 days post-fertilization, raised at 28°C on 16h light/8h dark cycle, 440 fish total |

### Fly and Locust Natural Behavior

> "Like many other insects (refs 29–32), fruit flies (ref 33) and desert locusts (ref 34) exhibit a natural tendency to orient and move toward high-contrast vertical features (potential landing sites or indicators of vegetation) in their environment."

Multiple identical black pillars were presented in an otherwise white environment.

### Experimental Protocols

**Fly experiments**:
- Each experimental trial lasted **15 minutes**
- Flies exposed to **five sets of stimuli**: three experimental sets and two control sets
- Experimental stimuli: 2 or 3 black cylinders in white environment
- Control stimulus: single pillar presented before and after experimental conditions

**Locust experiments**:
- Each experimental trial lasted **48 minutes**
- Three experimental sets (12 min each) and two control sets (6 min each)

**Fish experiments**:
- 198 fish: 2 virtual targets
- 39 fish: 3 equidistant virtual targets
- 50 fish: 3 targets in asymmetric geometry
- 20 min acclimatization, then 10 min control (single virtual conspecific circling in 8cm radius)
- 90 min choice experiments with virtual fish at random lateral distances and swim directions

### Key Experimental Results

#### Two-Choice Case

Both flies and locusts that choose one of the presented targets:
1. **Initially move in the average** of the egocentric target directions
2. Until a **critical angular difference**
3. At which point they **select (randomly) one or the other** option and move toward it

**Statistical validation**: "A randomization test where y coordinates between trajectories were swapped showed that the bifurcation fit to our experimental data was highly significant; **P < 0.01 for both flies and locusts**."

**Alternative hypothesis tested and rejected**:

> "Here, we note that there may be multiple factors that affect the animals' direction of movement. For example, it could be that animals repeatedly switch between fixating on each of the two options before reaching the critical angular difference, following which they select one. However, quantification of their heading relative to the targets and to the average direction between the targets finds no evidence for this; instead, prior to the bifurcation, both flies and locusts exhibit a heading toward the average of the egocentric target directions."

#### Three-Choice Case

Animals' movements consistent with theory:
- They **break the three-choice decision into two sequential binary decisions**
- **P < 10⁻⁴ for both flies and locusts**

#### Critical Angles Observed

| Organism | Critical Angle | Visual Spatial Resolution |
|----------|---------------|---------------------------|
| Flies | ~110° | ~8° |
| Locusts | ~90° | ~2° |

**Key observation**: Observed critical angles are **much larger than visual spatial resolution**.

#### Individual Variation (The ~30% Exception)

> "We note that ~30% of animals in our experiments (both flies and locusts) did not exhibit the sequential bifurcations described above and instead, moved directly toward one of the presented targets."

**Explanations offered**:

1. **Variation in directional tuning**: Consistent with recent work on visual response of flies demonstrating "a link between stochastic (nonheritable) variation in brain wiring within the visual system and strength of visual orientation response to a vertical stripe target" (ref 38).

2. **Developmental temperature effects**: "Flies that experience high temperatures during development appear to exhibit a particularly strong orientation tendency, exhibiting the most direct paths to targets, while flies that experience low developmental temperatures exhibit wandering paths to targets" (ref 39).

3. **"Handedness"**: "Approximately 25% of Drosophila were either strongly left biased or right biased when moving on a Y maze and that these consistent differences among flies were similarly nonheritable" (ref 40).

**Model explanation**: "In our model, such differences can be accounted for by variation in directional tuning of the neural groups, with high directional tuning (low ν) being associated with a strong orientational response and such individuals exhibiting direct tracks to targets from the outset."

**Prediction for future study** (verbatim):

> "We note that individuals predisposed to exhibit direct paths to targets would be expected to make faster, yet less accurate, decisions, a prediction we plan to test in future studies."

#### Track Classification

**Flies**: Classified as **direct tracks** vs. **nondirect tracks** based on time to reach target

**Locusts**: Three categories because virtual reality system allowed animals to stop and reconsider:
1. Direct tracks
2. Nondirect tracks
3. **Wandering tracks** (additional category)

### Zebrafish Results (Moving Frame of Reference)

Zebrafish experiments considered decision-making in a **social context** with virtual conspecifics that move back and forth parallel to each other.

**Key behavioral finding**: "Because they are social, the real fish respond to these virtual fish by tending to follow at a (relatively) fixed distance behind them."

**Two virtual fish prediction and result**:
- Should see single bifurcation where real fish suddenly switches from averaging target directions to deciding among them
- This occurs as a function of increasing the **lateral distance, L**, between virtual fish
- **Result**: "The existence of this bifurcation is clearly seen in our experiments"

**Three virtual fish prediction and result**:
- Model predicts real fish will spontaneously break three-choice decision into two binary decisions
- **Result**: "A comparison of the theoretical prediction and experimental results demonstrates this to be the case"

**Asymmetric geometry test** (Figure 4):

Setup: Two fish swim closer to each other than the central one does to the third fish (L₁₂ = 0.09m, L₂₃ = 0.03m)

Prediction: Real fish should treat the two closely associated fish as a single target

**Results** (verbatim):
> "As predicted by our theory, the real fish tends to swim between the two closely associated fish or close to the third more distant fish. Note that, also as predicted, the real fish spends a similar amount of time in each of the two locations."

---

## Essential Features for Bifurcation Patterns

### Feature 1: Feedback Processes

> "Feedback processes that provide the system directional persistence and drive such bifurcations are crucial to exhibit the observed spatiotemporal dynamics. In the neural system, this is present in the form of local excitation and long-range/global inhibition."

**Generalization**: "However, as shown in our model of collective animal behavior below, we expect that similar dynamics will be observed if the necessary feedbacks are also incorporated into other models of decision-making, such as to PDF sum–based models, for example."

### Feature 2: Recursive (Embodied) Interplay

> "Observing similar decision dynamics requires a recursive (embodied) interplay between neural dynamics and motion in continuous space. Here, the animal's geometrical relationship with the targets changes as it moves through physical space. Since neural interactions depend on this changing relationship, space provides a continuous variable by which the individual traverses the time-varying landscape of neural firing rates."

---

## Extension to Collective Decision-Making

### Why Standard Flocking Models Fail

> "A long-standing approach in the study of animal collectives is to consider them integrating vectorial information from neighbors, and there are a great number of publications of such 'flocking,' 'schooling,' or 'herding' behaviors."

**The failure** (verbatim):

> "We demonstrate here, however, that while ubiquitous, such models of collective animal behavior fail to account for the known capability for animal groups to make decisions among spatially discrete targets."

**The three-target problem**: In a three-target scenario, "vectors/votes to the leftmost option would tend to cancel those that favor the rightmost option, resulting in the selection of the central option."

### Solution: Incorporating Feedback Mechanisms

**Mechanism 1: Informed/Uninformed Individuals**

- "Informed" individuals (with desired direction of travel) associate with "uninformed" individuals (no specific desired direction)
- Uninformed individuals are **recruitable** (local positive feedback)
- **Finite supply** creates competition (effectively long-range inhibition)

**Limitation of this mechanism**:

> "However, because uninformed individuals tend to average the direction of all informed individuals that recruit them, we find that this type of feedback functions more as a social glue and is only able to explain bifurcations when the group is choosing between two options. In a decision-making context with three options, this type of feedback results in the group almost always moving toward the central target."

**Mechanism 2: Strength Adjustment (The Solution)**

> "A means of resolving this issue is for individuals to change the strength of their goal-orientedness as a function of their experienced travel direction; for example, individuals that find themselves consistently moving in a (group) direction that differs from their preferred target direction could weaken the strength of their preference over time [a form of forgetting/negative feedback, effectively resulting in long-range/global inhibition; when this preference is lost, they will tend to spontaneously reinforce the majority-selected direction, a form of positive feedback]."

**Result** (verbatim):

> "We find that this biologically plausible mechanism will allow individuals within the group to recover the capability to come to consensus even in the absence of uninformed individuals and for a greater number of options than two."

### Cross-Scale Similarity

**Critical finding** (verbatim):

> "Despite considerable differences in details between this model and that of neural dynamics described above, with the former involving individual components that change neighbor relationships over time and where inhibition emerges from a different biological process, the predictions regarding motion during decision-making are extremely similar."

**Conclusion**: "Thus, we find that similar principles may underlie spatial decision-making across multiple scales of biological organization."

**Three scales unified**:

> "Furthermore, by presenting social interactions in a decision-making context, our zebrafish experiments elucidate the neural basis of schooling, allowing us to glean insights across three scales of biological organization—from neural dynamics to individual decisions and from individual decisions to collective movement."

---

## Conclusions (Verbatim)

> "We demonstrate that, across taxa and contexts, explicitly considering the time-varying geometry during spatial decision-making provides insights that are essential to understand how and why animals move the way they do. The features revealed here are highly robust, and we predict that they occur in decision-making processes across various scales of biological organization, from individuals to animal collectives, suggesting they are fundamental features of spatiotemporal computation."

---

## Analysis Methods

### Trajectory Visualization

- Trajectories rotated so x-axis points from origin to center of mass of targets
- **Time-normalized density maps** created (proportion of maximum across sliding time window)
- Data **folded about line of symmetry, y = 0**
- Density threshold applied

### Bifurcation Quantification

**Piecewise phase transition function**:

```
y = { 0                  if x ≤ xc
    { A|x - xc|^α        if x > xc
```

Where:
- xc = critical point
- α = critical exponent
- A = proportionality constant

### Randomization Tests

Exact fit procedure conducted on randomized data (keeping x coordinates, swapping y coordinates with values from other random events).

Results show **highly significant** bifurcation fits:
- Binary choice: P < 0.01
- Three-choice: P < 10⁻⁴

---

## Connection to Ring Attractor Models

The paper notes the model is within the class of **neural ring attractor models**, which "like neural field models and attractor network models more generally, consider the collective firing activity of the neurons, or the firing rate, as opposed to the microscopic state of each firing neuron."

### Historical Context: Spin Systems in Neurobiology

> "Spin systems, which have been long studied in physics due to their ability to give insight into a wide range of collective phenomena from magnetic to quantum systems, were first introduced in the study of neurobiology by Hopfield in a landmark paper that provided considerable insights into principles underlying unsupervised learning and associative memory."

---

## Key References to Follow Up

| Reference | Topic | Citation Details |
|-----------|-------|------------------|
| Kim et al. 2017 (ref 7) | Ring attractor dynamics in Drosophila central brain | *Science* 356, 849-853 |
| Seelig & Jayaraman 2015 (ref 8) | Neural dynamics for landmark orientation and angular path integration | *Nature* 521, 186-191 |
| Sarel et al. 2017 (ref 11) | Vectorial representation of spatial goals in hippocampus of bats | *Science* 355, 176-180 |
| Bahl & Engert 2020 (ref 14) | Neural circuits for evidence accumulation and decision-making in larval zebrafish | *Nat. Neurosci.* 23, 94-102 |
| Pinkoviezky et al. 2018 (ref 15) | Collective conflict resolution in groups on the move | *Phys. Rev. E* 97, 032304 |
| Couzin et al. 2005 (ref 41) | Effective leadership and decision-making in animal groups on the move | *Nature* 433, 513-516 |
| Couzin et al. 2011 (ref 46) | Uninformed individuals promote democratic consensus in animal groups | *Science* 334, 1578-1580 |
| Hopfield 1982 (ref 57) | Neural networks and physical systems with emergent collective computational abilities | *PNAS* 79, 2554-2558 |
| Gelblum et al. 2015 (ref 22) | Ant groups optimally amplify effect of transiently informed individuals | *Nat. Commun.* 6, 7729 |
| Linneweber et al. 2020 (ref 38) | Neurodevelopmental origin of behavioral individuality in Drosophila visual system | *Science* 367, 1112-1119 |

---

## Data Availability

Animal movement data deposited in:
- GitHub: https://github.com/vivekhsridhar/GODM
- Zenodo: DOI 10.5281/zenodo.5599711

---

## Connections to Personal App / Implicit Behavioral Model

### Direct Parallels

| Couzin Framework | Personal App Application |
|------------------|-------------------------|
| Multiple spatial options | Multiple relational options (distance, conflict, engage, avoid) |
| Averaging vs. deciding | Ambivalence vs. behavioral commitment |
| Critical angular threshold | Anxiety threshold triggering mechanism selection |
| Bifurcation to one option | Commitment to one anxiety-binding mechanism |
| Sequential binary decisions | Complex relational situations decomposed into mechanism choices |
| Individual variation in directional tuning (ν) | Individual variation in default mechanisms |
| ~30% direct-path individuals | People with strong default mechanisms who don't deliberate |
| Stochastic nonheritable variation in brain wiring | Life experience shaping behavioral defaults |
| Faster but less accurate decisions for direct-path individuals | Reactive vs. thoughtful responders |
| Local excitation + global inhibition | Mechanism reinforcement + mutual exclusion |

### The Geometry of Relational Decisions

When facing relational anxiety, a person:
1. Initially "averages" — ambivalent, uncommitted
2. At a **critical threshold**, spontaneously commits to one mechanism
3. This commitment may trigger further decisions in sequence

**Example**: Family conflict situation
- Initial: ambivalence about how to respond
- Threshold reached: commits to distance (avoidance)
- Secondary: within distance, commits to specific avoidance behavior

### Neural Tuning as Mechanism Preference

The ν (neural tuning) parameter maps to **individual mechanism preference**:
- Low ν (high tuning) → strong preference, direct path to one mechanism
- High ν (low tuning) → more averaging, slower commitment, more exploration

**This is the "implicit behavioral model"** — the person's default tuning parameters for how they traverse decision space.

### Phase Transitions in Functioning

The paper's insight about **critical points** where systems become extremely sensitive applies to:
- Symptom onset (small stressor triggers cascade)
- Relationship shifts (small interaction tips into conflict)
- Anxiety binding (threshold where mechanism activates)

### Collective Dynamics in Family Systems

The paper's finding that collective decision-making follows the same principles as individual neural decision-making has direct implications:

- **Family systems are collective decision-making systems**
- The same bifurcation dynamics that operate at the neural level operate at the family level
- "Informed" vs. "uninformed" individuals maps to **differentiated** vs. **undifferentiated** family members
- The strength-adjustment mechanism (weakening goal-orientation when moving away from preferred direction) maps to **adaptive capacity** in family systems

### The "Forgetting" Mechanism

The paper describes how individuals who find themselves moving away from their preferred direction "weaken the strength of their preference over time" — this is a form of **adaptive updating** that allows collective consensus.

In Bowen theory terms: This maps to the capacity to **modify one's position** based on feedback from the system, rather than rigidly maintaining a stance that creates chronic tension.

---

## Key Conceptual Extraction for Synthesis

### 1. Sequential Binary Decomposition

The brain breaks complex multi-option decisions into binary decisions. The personal app should model relationship decisions similarly.

**Implication**: When a person faces a complex relational situation, they don't evaluate all options simultaneously. They implicitly reduce to binary choices in sequence.

### 2. Critical Thresholds (Tipping Points)

There exist points where small perturbations have large effects. These are the "tipping points" in functioning.

**Implication**: Symptom onset, relationship ruptures, and mechanism activation all occur at thresholds. Small differences at the threshold point can tip the decision.

### 3. Embodied Recursion

Decision and movement are coupled. In relationships, behavior and emotional state are coupled — each affects the other.

**Implication**: You cannot separate "what someone decided" from "how they moved through the situation." The trajectory *is* the decision process.

### 4. Individual Variation in Tuning

Some people have strong default mechanisms (direct path to distance, or to conflict). Others average longer before committing.

**The ~30% finding**: A significant minority don't show the deliberation phase at all. They go directly to their default mechanism.

**Implication**: Individual variation in "deliberation before commitment" is a key parameter of the implicit behavioral model.

### 5. Collective Dynamics Apply

The same principles that govern individual neural decisions govern group decisions. Family systems are collective decision-making systems.

**Implication**: The bifurcation dynamics seen in fish schools apply to families. Anxiety transmission, triangulation, and coalition formation can all be understood as collective bifurcation processes.

### 6. Speed-Accuracy Tradeoff

Direct-path individuals make faster but potentially less accurate decisions.

**Implication**: People with strong mechanism defaults react quickly but may not select the optimal response. This is a measurable individual difference.

### 7. Emergence of Discrimination Capacity

At the critical point, the system becomes capable of discriminating between very small differences. This is not built into the model — it **emerges**.

**Implication**: The capacity to make fine distinctions between relational options may itself be a threshold phenomenon. Below some anxiety level, the person can discriminate between subtle options. Above it, they collapse to coarse categories.

---

## Methodological Notes

### Virtual Reality Approach

- Immersive VR allowed precise control of options presented
- Could test both static (pillars) and moving (virtual conspecifics) targets
- Zebrafish experiments particularly relevant — social decision-making
- Virtual fish behaved and were responded to in the same way as real fish

### Analysis Method

- Density plots of trajectories
- Piecewise phase transition function fit to bifurcations
- Randomization tests for statistical significance
- Track classification (direct vs. nondirect vs. wandering)

---

## Document Status

**Captured**: Full 8-page paper with exhaustive extraction
**Date of exhaustive re-read**: 2026-01-04
**Next**: Await Patrick's implicit model presentation for cross-reference
**Synthesis pending**: Map Couzin geometry to Bowen theory mechanisms

---

## Figures Referenced

- **Figure 1**: Geometrical principles of two-choice and three-choice decision-making (schematics, phase diagrams, density plots for model and experiments)
- **Figure 2**: Decision-making for larger number of targets (4, 5, 6, 7 options)
- **Figure 3**: Decision-making in moving frame of reference (zebrafish with virtual conspecifics)
- **Figure 4**: Decision-making with targets in asymmetric geometry
- **Figure 5**: Consensus decision-making in simulations of animal groups

---

## Author Information

- Lead authors: Vivek H. Sridhar, Liang Li, Iain D. Couzin (corresponding)
- Institutions: Max Planck Institute of Animal Behavior, University of Konstanz, Weizmann Institute
- Contact: vivekhsridhar@gmail.com, lli@ab.mpg.de, icouzin@ab.mpg.de
