# Nollkaemper (2025) — "Avoid, Align or Contest?" Synthesis

**Full citation:** Andre Nollkaemper, "Avoid, Align or Contest? An Examination of National Courts' Postures in International Climate Law Litigation," *Transnational Environmental Law*, Vol. 14, Issue 3 (November 2025), pp. 469-499.
**DOI:** 10.1017/S2047102525100058
**Access:** Open Access
**Affiliation:** SEVEN, University of Amsterdam

---

## Origin of the Typology

The three-part typology (Avoid, Align, Contest) was originally developed by the **ILA Study Group on "Principles on the Engagement of Domestic Courts with International Law"** (2011-2016), led by Antonios Tzanakopoulos, with Nollkaemper, Yuval Shany, and Eleni Methymaki. Final Report presented at the ILA Johannesburg Conference 2016.

Further elaborated in: Nollkaemper, A., Shany, Y., Tzanakopoulos, A. & Methymaki, E. (eds.), *The Engagement of Domestic Courts with International Law: Comparative Perspectives* (Oxford University Press, 2024). ISBN: 9780192864185.

Nollkaemper adapted this general international law typology to the climate litigation context in the TEL article.

---

## Dataset

- **148 cases** identified where plaintiffs invoked international climate law (UNFCCC, Kyoto Protocol, Paris Agreement)
- **39 pending** (no judgment) → **109 with judgments** analyzed
- **10 cases**: courts decided on domestic law alone (indirect engagement)
- **13 instances**: both preliminary and final decisions coded separately
- Described as "the first systematic appraisal" of national courts' responses to international climate law

---

## The Three Postures

### A. AVOIDANCE

Courts sidestep the international climate law question and refrain from ruling on the merits.

**Sub-types:**

1. **Not part of domestic law (dualism / lack of direct effect)**
   - *Dualist states:* treaties apply only if incorporated into national law
   - *Monist states:* lack of "direct effect" as a barrier

2. **Lack of standing**
   - Plaintiffs lacked standing to bring a claim under international climate law
   - Public interest standing rules are the key variable

3. **Separation of powers / political branches**
   - Application of international climate law deemed a matter for political branches
   - Described as "a decisive background variable" underlying other avoidance strategies

### B. ALIGNMENT

Courts interpret domestic law in light of international climate law, or treat international climate norms as relevant factors.

**Sub-types:**

1. **Fair weather alignment** (most common)
   - Harmonize domestic law with international law when no political tension exists

2. **Consubstantial alignment**
   - Rely on domestic norms (e.g., constitutional rights, human rights) whose content is informed by Paris Agreement benchmarks
   - Key mechanism: courts can enforce Paris-derived standards without formally "applying" international law
   - *Example:* **Urgenda** — Dutch Supreme Court used Paris Agreement / COP targets to interpret duty of care under ECHR Articles 2 & 8

3. **Overriding alignment** (rare)
   - Apply international law even where it conflicts with domestic law

4. **Hyper-alignment** (very rare)
   - Go beyond what international law requires

### C. CONTESTATION

Courts engage with international climate law on the merits but then reject or reinterpret it. Unlike avoidance (which sidesteps), contestation involves engagement followed by refusal.

**Sub-types:**
- **Interpretive contestation:** reinterpret international norms to narrow their scope
- **Treaty override:** constitutional acceptance of contrary domestic legislation
- **Non-compliance:** refuse to apply binding international decisions

*Example:* **Shell v Milieudefensie (2024)** — Hague Court of Appeal overturned the 2021 ruling that had used alignment-based reasoning.

**Mixed postures:** Nollkaemper notes "contestation-cum-alignment" and "alignment-cum-contestation" — cases can bear marks of both postures simultaneously.

### Additional Category: INDIRECT ENGAGEMENT

In 10 of 148 cases, courts engaged with norms derived from international climate law *as domestic law* — not expressly engaging with international law. Discussed separately and excluded from the three-posture analysis.

---

## Key Findings

1. **Avoidance is the dominant posture** across all jurisdictions
2. **Alignment is rare but impactful** — landmark cases advance Paris Agreement objectives
3. **Contestation exists but is less documented**
4. **National legal context is determinative** — constitutional framework (monist/dualist, standing, separation of powers) is the primary variable
5. **International law succeeds when embedded in domestic law** — alignment occurs when international arguments are blended with domestic claims
6. **U.S. cases are notable for avoidance** — US courts rarely engage with international climate law

---

## Relevance to phdMutley Pipeline

### Current functional categories (Phase 2B):
- `parties_argument`: court recounts what a party argued
- `dismissed`: court rejects or distinguishes the citation
- `contributed`: citation supports the court's own reasoning

### Proposed adaptation using Nollkaemper's typology:

The Nollkaemper typology classifies **how courts respond to international law arguments**, while our Phase 2B classifies **how a citation is used in the judgment**. These are complementary but operate at different levels:

- **Nollkaemper** = document-level posture (one classification per case)
- **Phase 2B** = citation-level function (one classification per citation)

**Proposed mapping for Phase 2B (citation-level):**

| Current Category | Proposed Replacement | Nollkaemper Parallel | Definition |
|-----------------|---------------------|---------------------|------------|
| `parties_argument` | `invoked` | (Pre-posture) | The citation is recounted as a party's argument, not the court's own reasoning |
| `dismissed` | `contested` | Contestation | The court engages with the cited case but rejects, distinguishes, or reinterprets it |
| `contributed` | `aligned` | Alignment | The citation supports or informs the court's reasoning |
| *(new)* | `avoided` | Avoidance | The citation is mentioned but the court declines to engage with it substantively (e.g., "not applicable here", non-justiciable) |

This gives us **academically grounded** categories with a published theoretical basis (ILA Study Group → Nollkaemper 2025), while preserving the citation-level granularity our pipeline needs.

---

## References

- Nollkaemper (2025): DOI 10.1017/S2047102525100058
- ILA Study Group Final Report: Johannesburg 2016
- OUP (2024): *The Engagement of Domestic Courts with International Law*, ISBN 9780192864185
