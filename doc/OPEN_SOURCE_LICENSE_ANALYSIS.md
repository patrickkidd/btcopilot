# Open Source License Recommendation for btcopilot

## Recommended License: AGPL-3.0 (GNU Affero General Public License)

Why AGPL over MIT/Apache:

- **Network clause**: Anyone who runs a modified version as a service must release their source code
- **Copyleft**: Derivatives must also be AGPL, preventing proprietary forks
- **Discourages commercial theft**: Companies can't just take it and compete without contributing back

This provides visibility (recruiters, domain experts can see everything) while creating legal friction for anyone trying to profit from it.

## Theft Risk Assessment

The theft risk is lower than it appears. Reasons:

### 1. Execution > Source Code

The codebase is complex (Qt/QML desktop app + Flask backend + prompt engineering + clinical domain model). Someone would need:

- Deep understanding of Bowen theory and SARF
- Prompt engineering expertise for clinical extraction
- The patience to build and maintain the GT dataset
- The domain credibility to market to family therapists

### 2. The real moat is GT + prompts

The F1 score didn't come from clever algorithms; it came from iterating on ground truth with domain expertise. That's not in the source code.

### 3. Who would steal it?

The Venn diagram of "people who understand Bowen theory deeply enough to maintain this" and "people willing to steal open source code to compete" is essentially empty.

### 4. The "they think they get it but don't" problem

This is the biggest protection. SARF looks simple until you try to implement it. The subtlety is in the taxonomy, the edge cases, the clinical judgment calls embedded in the GT.

## The Real Risk

The risk isn't a competitor copying the code. It's:

- A well-funded startup building something similar from scratch with better marketing
- AI advances making the extraction problem trivially solvable without this specific approach

Neither of those is prevented by keeping source closed.

## Recommendation

1. **Keep fdserver private** (deployment, keys, proprietary training data, GT dataset)
2. **AGPL for btcopilot** (already open source - includes prompts.py)
3. **AGPL for familydiagram** (the desktop app)

The GT dataset in fdserver is the primary IP. The prompts in btcopilot are public but less valuable without the GT iteration history and domain expertise to tune them.

## Bottom Line

The people who would steal this code couldn't execute on it. The people who could execute on it don't need the code. The visibility benefits (recruiting, domain review, credibility) are real and immediate.
