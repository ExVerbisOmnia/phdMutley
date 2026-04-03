# Meeting Report — Research & Pipeline Strategy

**Date:** 27 March 2026
**Participants:** Gustavo Rodriguez, Lucas Biasetton
**Scope:** Topics 5–10 from the touchpoint meeting — covering the Global Trends deliverable, pipeline improvement strategy, and the Transnational Environmental Law article direction.

---

## 1. Global Trends Box — Data & Methodology

### Context

Kate emailed about the Global Trends box, raising the question of whether to use Gustavo's newer extraction data or the older dataset that was manually reviewed in Claude. The decision affects data quality and consistency for the deliverable.

### The Juliana Case Problem

A key methodological issue was identified: the same case can be litigated across multiple courts (domestic and international instances). The **Juliana v. United States** case is a concrete example — it has been cited both as a domestic US case and in international contexts.

- **When systematic:** The citing court's name in the citation text can disambiguate which instance is being referenced.
- **When unsystematic:** Inference is required. For example, an Inter-American Court of Human Rights judge citing a case that was also heard at the European Court of Human Rights — the citation may not specify which proceeding.

This is a classification problem that affects the accuracy of the sixfold citation typology.

### Timeline & Constraints

| Constraint               | Detail                    |
| ------------------------ | ------------------------- |
| Final deadline           | Early May 2026            |
| Lucas unavailable from   | 10 April 2026             |
| Effective working window | ~12 days (27 Mar – 9 Apr) |

### Decision

- **Primary path:** Improve the extraction pipeline with Gemini, fixing inconsistencies identified in the 2nd run, and execute a quality re-extraction.
- **Contingency:** Compare the two extractions (old vs. new) in Claude if results are inconclusive or time runs out.

---

## 2. AI Agent for Data Verification

### Proposal

Lucas proposed creating an AI agent to assist in validating extraction results — a role currently filled by Kate's manual review. The agent would:

1. Ingest Lucas's domain knowledge as structured rules
2. Run automated checks against the extracted citation database
3. Flag anomalies, misclassifications, and edge cases for human review

### Feasibility

Gustavo confirmed this is technically feasible using Claude. The approach:

- Configure the agent with a rule set derived from Lucas's expertise
- Register known edge cases (e.g., multi-instance litigation)
- Run the agent as a verification pass after each extraction batch

### Agreed Plan

```
Improve pipeline (Gemini) → Add rules for edge cases → Create verification agent
```

The verification agent is positioned as a complement to, not a replacement for, human review — it reduces the volume of citations requiring manual inspection.

---

## 3. Knowledge Integration & Rule Documentation

### The Problem

Accumulated knowledge from prior extraction runs (v1 through v7) exists only in code, commit history, and the researchers' heads. This creates risk: rules are implicit, corner cases are undocumented, and pipeline improvements may inadvertently regress on previously solved problems.

### Documentation Plan

| Step                  | Owner   | Description                                                                                       |
| --------------------- | ------- | ------------------------------------------------------------------------------------------------- |
| 1. Document algorithm | Gustavo | Translate the pipeline logic and extraction rules into structured, human-readable language        |
| 2. Review & annotate  | Lucas   | Review the documentation, adding corner cases, edge case rules, and domain-specific exceptions    |
| 3. Apply to pipeline  | Gustavo | Encode the revised rule set back into the main and secondary extraction pipelines                 |
| 4. Iterative testing  | Both    | Run small batches, review results (manually + with agent), iterate until confidence is sufficient |
| 5. Full run           | Gustavo | Execute on the complete dataset                                                                   |

### Timeline Estimate

- ~1 week for the full dataset run (after documentation and testing cycles are complete)
- Must be completed within the 12-day working window before Lucas's absence

---

## 4. Transnational Environmental Law Article (Florence)

### Opportunity

A conference on **Transnational Environmental Law** in Florence, organized by **Cambridge University Press**. Format: draft papers (work-in-progress is acceptable).

| Field               | Detail                     |
| ------------------- | -------------------------- |
| Organizer           | Cambridge University Press |
| Location            | Florence, Italy            |
| Submission deadline | **13 April 2026**          |
| Format              | Draft paper                |

### Relevant Conference Themes

Two themes from the call for papers were identified as strong fits:

1. **"The role of courts, regulators, and private actors"** — directly aligned with the citation analysis of judicial dialogue
2. **"Digitization, AI, and new technologies in environmental governance"** — aligned with the methodology (AI-driven large-scale citation extraction and classification)

### Angle Evolution

Lucas's thinking on the article angle evolved during the discussion:

1. **Initial idea:** Catalytic cases → **discarded**
2. **Second idea:** Reuse the Columbia submission (methodology + citation clusters) → debated whether methodology-only is attractive enough
3. **Final direction:** A more conceptual framing — how intercourt dialogue in climate litigation is constructing a new global environmental governance (see next section)

### Reviewer Alignment

Lucas used Claude to research the journal reviewers' research preferences, which could help frame the paper to dialogue with the editorial board's interests.

---

## 5. Article Direction — Intercourt Dialogue & Global Environmental Governance

### Core Research Question

> How is transnational judicial dialogue in climate litigation constructing a new form of global environmental governance? What does this dialogue reveal about which subjects require international coordination, and where are the gaps?

### Analytical Framework

The proposed approach combines two layers:

1. **Quantitative:** Use the phdMutley citation database to identify clusters, patterns, and asymmetries in intercourt citation behavior (e.g., US cites no one, Brazil cites everyone, 96% Global North / 4% Global South)
2. **Qualitative:** Deep-dive into the substance of what is being cited — which legal concepts, doctrines, and narratives travel across jurisdictions

### Key Arguments Discussed

#### Courts as central actors in climate governance

- International agreements are weakening (US exit from Paris Agreement)
- Despite this, climate change remains an urgent problem
- The debate has shifted to national courts, which continue to judge climate cases with vigor
- These courts often interpret the same international norms, creating de facto coordination

#### Chain of environmental protection

Gustavo outlined a multi-level chain:

- **International norms** → internalized by national courts → applied domestically
- **Treaties** → applied directly by international courts
- **Intercourt dialogue** occurs at multiple levels: international ↔ national, national ↔ national, international ↔ international

#### Subjects demanding cooperation

- The dialogue may reveal which legal subjects require international uniformity or generate the most uncertainty
- In complex climate cases (e.g., attribution science), national precedent often doesn't exist — courts seek foreign precedents
- This creates a functional need for intercourt dialogue

#### Normative support in treaties

- Open question: Do international instruments (e.g., Paris Agreement) contain provisions mandating coordination or collaboration between courts?
- If such provisions exist, they provide robust normative backing for the argument that intercourt dialogue is not just happening but is legally expected
- Lucas committed to researching this

#### Narratives as vehicles of dialogue

- Lucas referenced an article about how narratives of climate cases migrate internationally
- Hypothesis: transnational judicial dialogue may occur through case narratives rather than hard law — a softer, less formal mechanism of legal transplantation

#### Cases against companies vs. cases against states

- Preliminary data suggests that litigation against private companies draws on precedents from litigation against states
- This cross-pollination between case types is a potentially novel finding

### Methodological Flexibility

Gustavo encouraged Lucas not to restrict the article exclusively to intercourt dialogue. The database and analytical tools can support laterally related topics — the data should guide the framing, not the other way around.

---

## 6. Next Steps for the Article

### Division of Labor

| Owner   | Task                                                                          | Deadline               |
| ------- | ----------------------------------------------------------------------------- | ---------------------- |
| Lucas   | Send thesis qualification project to Gustavo (full context + references)      | ASAP                   |
| Lucas   | Develop a possible article direction and preliminary structure                | Before next touchpoint |
| Gustavo | Explore the citation database for patterns that support the proposed angle    | Before next touchpoint |
| Both    | Research treaty provisions on intercourt coordination (Paris Agreement, etc.) | Before submission      |

### Strategic Context

- Lucas's thesis deposit deadline is **2029** — there is no urgency to lock into a narrow framing
- The Florence submission (13 April) is an opportunity to test an early-stage argument in a supportive format (draft papers)
- Both agreed to maintain flexibility in topic selection — the data and analysis may reveal a more compelling angle than what was discussed

---

## Summary of Decisions

| #   | Decision                                                                    | Rationale                                                                   |
| --- | --------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| D23 | Improve pipeline before full re-extraction                                  | Fix inconsistencies from 2nd run; more effective than comparing old vs. new |
| D24 | Document extraction rules in human-readable format before coding            | Ensures Lucas can review and add domain knowledge before it's encoded       |
| D25 | Create AI verification agent                                                | Reduces manual review burden; leverages Lucas's rules at scale              |
| D26 | Run iterative small batches before full dataset run                         | Build confidence incrementally; catch errors early                          |
| D27 | Article angle: intercourt dialogue building global environmental governance | Combines quantitative (DB) + qualitative analysis; fits Florence themes     |
| D28 | Maintain flexibility on article framing                                     | Data should guide the final angle; thesis deadline is 2029                  |
