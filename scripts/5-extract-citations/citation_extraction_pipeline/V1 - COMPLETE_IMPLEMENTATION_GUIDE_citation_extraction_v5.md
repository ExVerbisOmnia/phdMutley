# Complete Implementation Guide - Citation Extraction v5 (Phased Approach)
## Enhanced Foreign Case Law Capture

**Project:** PhD Climate Litigation - Citation Analysis  
**Date:** November 22, 2025  
**Status:** READY FOR IMPLEMENTATION  
**Script:** `extract_citations_v5_phased.py`

---

## 🎯 QUICK START FOR NEW CHAT

**Start your next chat with:**
```
I need to implement the phased citation extraction v5 with enhanced foreign case law capture.
Please read /mnt/user-data/outputs/COMPLETE_IMPLEMENTATION_GUIDE_citation_extraction_v5.md
Let's begin with creating the database schema and Phase 1 implementation.
```

---

## 📋 EXECUTIVE SUMMARY

### Problem Statement
Current single-pass extraction (v4) achieves only 40-50% recall for foreign citations because the LLM over-filters during extraction.

### Solution: 4-Phase Architecture
1. **Phase 1:** Source jurisdiction identification (from database)
2. **Phase 2:** Extract ALL case law references (no filtering)
3. **Phase 3:** Identify case origin (3-tier approach)
4. **Phase 4:** Classify citation type (comparison logic)

### Expected Improvement
- **Current:** 40-50% recall, 95% precision
- **Target:** 75-85% recall, 85-90% precision
- **Cost:** Similar (~$0.02-0.05 per document)

---

## 🏗️ PHASE 1: SOURCE JURISDICTION

### Implementation Code
```python
def get_source_jurisdiction(geographies_string):
    """
    Extract primary jurisdiction from Geographies field.
    
    INPUT: "United States; California; Washington, D.C."
    ALGORITHM:
        1. Split by semicolon
        2. Take first value (country level)
        3. Handle international tribunals
    OUTPUT: Primary country string
    """
    if not geographies_string:
        return "Unknown"
    
    parts = [p.strip() for p in geographies_string.split(';')]
    primary = parts[0]  # Country level only
    
    # Check if international
    if primary in ['International', 'INTL', 'World']:
        return "International"
    
    return primary

def get_source_region(country):
    """Classify as Global North/South/International"""
    # Use existing classification from config.py
    pass
```

---

## 📝 PHASE 2: ENHANCED EXTRACTION

### 2.1 Complete Citation Format List

```python
CITATION_FORMATS = {
    # EXISTING FORMATS (from v4)
    "traditional": {
        "pattern": r"[\w\s]+v\.?\s+[\w\s]+,?\s*\d+\s+[\w\.\s]+\d+",
        "example": "Brown v. Board of Education, 347 U.S. 483 (1954)"
    },
    
    "narrative": {
        "pattern": "court_name + held/ruled/decided + date/year",
        "example": "The Norwegian Supreme Court held in its 2020 petroleum decision"
    },
    
    "shorthand": {
        "pattern": "the [Name] case/decision/approach",
        "example": "the Urgenda case"
    },
    
    "scholarly": {
        "pattern": "author + analysis/discusses + case_name",
        "example": "Setzer & Vanhala (2019) note regarding Urgenda"
    },
    
    "procedural": {
        "pattern": "on appeal from / affirmed by / reversed by",
        "example": "On appeal from the District Court of The Hague"
    },
    
    "comparative": {
        "pattern": "unlike/similar to/drawing on + case",
        "example": "Similar to the reasoning in Massachusetts v. EPA"
    },
    
    # NEW FORMATS TO ADD
    "parallel_citations": {
        "pattern": "case_name + multiple_citation_formats",
        "example": "Urgenda (ECLI:NL:HR:2019:2007; [2020] 2 CMLR 1)"
    },
    
    "translated_names": {
        "pattern": "translated case names in English",
        "example": "the Climate Case (Klimaatzaak)"
    },
    
    "footnote_citations": {
        "pattern": "citations in footnotes/endnotes",
        "example": "See supra note 42"
    },
    
    "signal_citations": {
        "pattern": "see also / cf. / compare with",
        "example": "Cf. Juliana v. United States"
    },
    
    "dissenting_citations": {
        "pattern": "citations in dissenting/concurring opinions",
        "example": "As Justice X noted in dissent, citing Urgenda"
    },
    
    "doctrine_references": {
        "pattern": "legal doctrine implying case law",
        "example": "applying the precautionary principle as developed in European jurisprudence"
    },
    
    "advisory_opinions": {
        "pattern": "ICJ/other advisory opinions",
        "example": "ICJ Advisory Opinion on Climate Change"
    },
    
    "pending_cases": {
        "pattern": "cases pending/ongoing",
        "example": "pending before the European Court"
    }
}
```

### 2.2 Enhanced Extraction Prompt

```python
def generate_phase2_extraction_prompt(text, source_jurisdiction):
    """
    Generate comprehensive extraction prompt for Phase 2.
    
    KEY PRINCIPLE: Extract EVERYTHING - no filtering for foreign/domestic.
    """
    
    prompt = f"""You are extracting ALL judicial decision references from a legal document.
The source court is from: {source_jurisdiction}

CRITICAL: Extract EVERY reference to case law, regardless of whether it's domestic or foreign.
Do NOT filter by jurisdiction - we will classify that later.

<extraction_patterns>
1. Traditional Citations
   - "Brown v. Board of Education, 347 U.S. 483 (1954)"
   - "R (Miller) v Secretary of State [2017] UKSC 5"
   - Include ALL citation formats (parallel citations, alternative reporters)

2. Narrative References
   - "The Norwegian Supreme Court held in 2020..."
   - "Following the Dutch court's approach in..."
   - "The Oslo District Court ruled on [date]..."

3. Shorthand References
   - "the Urgenda case"
   - "following Abraham"
   - "the landmark Dutch climate decision"

4. Scholarly Citations
   - "Professor X's analysis of the Urgenda case"
   - "As noted by UNEP regarding the Norwegian ruling"

5. Procedural References
   - "On appeal from..."
   - "Affirmed by..."
   - "Following reversal by..."

6. Comparative References
   - "Unlike the approach in..."
   - "Similar to..."
   - "Distinguishing..."

7. Signal Citations
   - "See also..."
   - "Cf..."
   - "Compare with..."

8. Footnote/Endnote Citations
   - Include ALL citations in footnotes
   - Include "supra" and "infra" references

9. Dissenting/Concurring Opinion Citations
   - Include citations from ALL opinion types

10. Doctrine References
    - References to legal principles developed in specific jurisdictions
    - "European precautionary principle jurisprudence"

11. Advisory Opinions
    - ICJ Advisory Opinions
    - Other international tribunal advisory opinions

12. Pending/Ongoing Cases
    - "pending before..."
    - "currently before..."
</extraction_patterns>

<context_capture>
For EACH citation found, capture:
1. The complete citation text
2. The 2-3 sentences BEFORE the citation
3. The 2-3 sentences AFTER the citation
4. The section heading where it appears
5. Whether it's in main text, footnote, or opinion type
</context_capture>

<output_format>
{{
  "case_law_references": [
    {{
      "case_name": "extracted case name",
      "raw_text": "complete citation as it appears",
      "format": "traditional|narrative|shorthand|etc",
      "context_before": "2-3 sentences before",
      "context_after": "2-3 sentences after",
      "section": "section heading if available",
      "location": "main_text|footnote|dissent|concurrence",
      "confidence": 0.0-1.0
    }}
  ],
  "total_references_found": number,
  "sections_with_citations": ["list of sections"]
}}
</output_format>

REMEMBER: Extract EVERYTHING that looks like case law. Do NOT filter.

Document text:
{text}"""
    
    return prompt
```

---

## 🔍 PHASE 3: ENHANCED ORIGIN IDENTIFICATION

### 3.1 Expanded Court Database

```python
KNOWN_FOREIGN_COURTS = {
    # EUROPEAN COURTS
    "Court of Session": {"country": "Scotland", "type": "Appellate"},
    "Inner House": {"country": "Scotland", "type": "Appellate"},
    "Outer House": {"country": "Scotland", "type": "Trial"},
    "High Court of Justiciary": {"country": "Scotland", "type": "Criminal Supreme"},
    "The Hague Court": {"country": "Netherlands", "type": "Trial", "formal": "District Court of The Hague"},
    
    # NORDIC COURTS
    "Oslo District Court": {"country": "Norway", "type": "Trial"},
    "Oslo tingrett": {"country": "Norway", "type": "Trial"},
    "Borgarting Court of Appeal": {"country": "Norway", "type": "Appellate"},
    "Supreme Court of Norway": {"country": "Norway", "type": "Supreme"},
    "Høyesterett": {"country": "Norway", "type": "Supreme"},
    "Norges Høyesterett": {"country": "Norway", "type": "Supreme"},
    
    # IRISH COURTS & TRIBUNALS
    "An Bord Pleanála": {"country": "Ireland", "type": "Administrative"},
    "High Court of Ireland": {"country": "Ireland", "type": "Trial"},
    "Irish Supreme Court": {"country": "Ireland", "type": "Supreme"},
    "Court of Appeal of Ireland": {"country": "Ireland", "type": "Appellate"},
    
    # DUTCH COURTS
    "Hoge Raad": {"country": "Netherlands", "type": "Supreme"},
    "Dutch Supreme Court": {"country": "Netherlands", "type": "Supreme"},
    "District Court of The Hague": {"country": "Netherlands", "type": "Trial"},
    "Rechtbank Den Haag": {"country": "Netherlands", "type": "Trial"},
    "Gerechtshof Den Haag": {"country": "Netherlands", "type": "Appellate"},
    
    # FRENCH COURTS
    "Conseil d'État": {"country": "France", "type": "Administrative Supreme"},
    "Council of State": {"country": "France", "type": "Administrative Supreme"},
    "Cour de cassation": {"country": "France", "type": "Supreme"},
    "Tribunal administratif": {"country": "France", "type": "Administrative Trial"},
    
    # GERMAN COURTS
    "Bundesverfassungsgericht": {"country": "Germany", "type": "Constitutional"},
    "Federal Constitutional Court": {"country": "Germany", "type": "Constitutional"},
    "BVerfG": {"country": "Germany", "type": "Constitutional"},
    "Bundesgerichtshof": {"country": "Germany", "type": "Supreme"},
    "BGH": {"country": "Germany", "type": "Supreme"},
    
    # INTERNATIONAL COURTS/TRIBUNALS
    "European Court of Justice": {"country": "International", "type": "Regional", "jurisdiction": ["EU"]},
    "Court of Justice of the European Union": {"country": "International", "type": "Regional", "jurisdiction": ["EU"]},
    "CJEU": {"country": "International", "type": "Regional", "jurisdiction": ["EU"]},
    "ECJ": {"country": "International", "type": "Regional", "jurisdiction": ["EU"]},
    "General Court": {"country": "International", "type": "Regional", "jurisdiction": ["EU"]},
    "Court of First Instance": {"country": "International", "type": "Regional", "jurisdiction": ["EU"]},
    
    "European Court of Human Rights": {"country": "International", "type": "Regional", "jurisdiction": ["Council of Europe"]},
    "ECtHR": {"country": "International", "type": "Regional", "jurisdiction": ["Council of Europe"]},
    "ECHR": {"country": "International", "type": "Regional", "jurisdiction": ["Council of Europe"]},
    
    "Inter-American Court of Human Rights": {"country": "International", "type": "Regional", "jurisdiction": ["OAS"]},
    "IACHR": {"country": "International", "type": "Regional", "jurisdiction": ["OAS"]},
    "Inter-American Commission": {"country": "International", "type": "Regional", "jurisdiction": ["OAS"]},
    
    "African Court on Human and Peoples' Rights": {"country": "International", "type": "Regional", "jurisdiction": ["AU"]},
    "ACHPR": {"country": "International", "type": "Regional", "jurisdiction": ["AU"]},
    "African Commission": {"country": "International", "type": "Regional", "jurisdiction": ["AU"]},
    "East African Court of Justice": {"country": "International", "type": "Regional", "jurisdiction": ["EAC"]},
    
    "International Court of Justice": {"country": "International", "type": "Global"},
    "ICJ": {"country": "International", "type": "Global"},
    "International Criminal Court": {"country": "International", "type": "Global"},
    "ICC": {"country": "International", "type": "Global"},
    "International Tribunal for the Law of the Sea": {"country": "International", "type": "Global"},
    "ITLOS": {"country": "International", "type": "Global"},
    
    # UN TREATY BODIES
    "Human Rights Committee": {"country": "International", "type": "Treaty Body", "jurisdiction": ["ICCPR"]},
    "Committee on the Rights of the Child": {"country": "International", "type": "Treaty Body", "jurisdiction": ["CRC"]},
    "Committee on Economic, Social and Cultural Rights": {"country": "International", "type": "Treaty Body", "jurisdiction": ["ICESCR"]},
    
    # COMMONWEALTH COURTS
    "Privy Council": {"country": "International", "type": "Commonwealth", "jurisdiction": ["Commonwealth"]},
    "JCPC": {"country": "International", "type": "Commonwealth", "jurisdiction": ["Commonwealth"]},
    "Judicial Committee of the Privy Council": {"country": "International", "type": "Commonwealth", "jurisdiction": ["Commonwealth"]},
    
    "Supreme Court of Canada": {"country": "Canada", "type": "Supreme"},
    "Federal Court of Canada": {"country": "Canada", "type": "Federal"},
    "High Court of Australia": {"country": "Australia", "type": "Supreme"},
    "Federal Court of Australia": {"country": "Australia", "type": "Federal"},
    "Supreme Court of New Zealand": {"country": "New Zealand", "type": "Supreme"},
    "Constitutional Court of South Africa": {"country": "South Africa", "type": "Constitutional"},
    
    # LATIN AMERICAN COURTS
    "Supremo Tribunal Federal": {"country": "Brazil", "type": "Constitutional"},
    "STF": {"country": "Brazil", "type": "Constitutional"},
    "Superior Tribunal de Justiça": {"country": "Brazil", "type": "Superior"},
    "STJ": {"country": "Brazil", "type": "Superior"},
    "Corte Suprema de Justicia": {"country": "Colombia", "type": "Supreme"},
    "Corte Constitucional": {"country": "Colombia", "type": "Constitutional"},
    
    # ASIAN COURTS
    "Supreme Court of India": {"country": "India", "type": "Supreme"},
    "National Green Tribunal": {"country": "India", "type": "Environmental"},
    "Supreme Court of Pakistan": {"country": "Pakistan", "type": "Supreme"},
    "Lahore High Court": {"country": "Pakistan", "type": "High Court"},
    "Green Bench": {"country": "Pakistan", "type": "Environmental"},
    
    # US COURTS (for identification)
    "United States Supreme Court": {"country": "United States", "type": "Supreme"},
    "SCOTUS": {"country": "United States", "type": "Supreme"},
    "Ninth Circuit": {"country": "United States", "type": "Appellate"},
    "Second Circuit": {"country": "United States", "type": "Appellate"},
}
```

### 3.2 Enhanced Landmark Cases Database

```python
LANDMARK_CLIMATE_CASES = {
    "Urgenda": {
        "full_name": "Urgenda Foundation v. State of the Netherlands",
        "court": "Supreme Court of the Netherlands",
        "country": "Netherlands",
        "years": [2015, 2018, 2019],
        "alternative_names": ["Urgenda case", "Dutch climate case", "Urgenda litigation", "Urgenda approach"],
        "translations": {"Dutch": "Urgenda-zaak", "German": "Urgenda-Urteil"}
    },
    
    "Massachusetts": {
        "full_name": "Massachusetts v. Environmental Protection Agency",
        "court": "Supreme Court of the United States",
        "country": "United States",
        "years": [2007],
        "citation": "549 U.S. 497",
        "alternative_names": ["Massachusetts v. EPA", "Mass v. EPA"]
    },
    
    "Juliana": {
        "full_name": "Juliana v. United States",
        "court": "United States District Court / Ninth Circuit",
        "country": "United States",
        "years": [2015, 2020],
        "alternative_names": ["Youth climate case", "Our Children's Trust case"]
    },
    
    "Plan B": {
        "full_name": "Plan B Earth and Others v. Prime Minister",
        "court": "High Court / Court of Appeal (England and Wales)",
        "country": "United Kingdom",
        "years": [2020],
        "alternative_names": ["Heathrow Third Runway case", "Plan B case"]
    },
    
    "Leghari": {
        "full_name": "Leghari v. Federation of Pakistan",
        "court": "Lahore High Court",
        "country": "Pakistan",
        "years": [2015],
        "alternative_names": ["Pakistani farmer case", "Leghari case"]
    },
    
    "Neubauer": {
        "full_name": "Neubauer et al. v. Germany",
        "court": "Federal Constitutional Court",
        "country": "Germany",
        "years": [2021],
        "alternative_names": ["German climate case", "Klimaschutz decision"],
        "translations": {"German": "Klimabeschluss"}
    },
    
    "Sharma": {
        "full_name": "Sharma v. Minister for the Environment",
        "court": "Federal Court of Australia",
        "country": "Australia",
        "years": [2021],
        "alternative_names": ["Australian youth case", "Sharma case"]
    },
    
    "Shell": {
        "full_name": "Milieudefensie et al. v. Royal Dutch Shell",
        "court": "District Court of The Hague",
        "country": "Netherlands",
        "years": [2021],
        "alternative_names": ["Shell climate case", "Milieudefensie case"]
    },
    
    "Nature and Youth Norway": {
        "full_name": "Nature and Youth Norway v. The State of Norway",
        "court": "Supreme Court of Norway",
        "country": "Norway",
        "years": [2020],
        "alternative_names": ["Norwegian climate case", "Arctic oil case"]
    },
    
    "Greenpeace Nordic": {
        "full_name": "Greenpeace Nordic v. The State of Norway",
        "court": "Oslo District Court",
        "country": "Norway",
        "years": [2024],
        "alternative_names": ["Greenpeace Norway case", "Norwegian petroleum case"]
    },
    
    "Grande-Synthe": {
        "full_name": "Commune de Grande-Synthe v. France",
        "court": "Conseil d'État",
        "country": "France",
        "years": [2021],
        "alternative_names": ["French municipality case", "Grande-Synthe case"]
    },
    
    "Torres Strait": {
        "full_name": "Torres Strait Islanders v. Australia",
        "court": "UN Human Rights Committee",
        "country": "International",
        "years": [2022],
        "alternative_names": ["Torres Strait case", "Australian islands case"]
    },
    
    "KlimaSeniorinnen": {
        "full_name": "KlimaSeniorinnen v. Switzerland",
        "court": "European Court of Human Rights",
        "country": "International",
        "years": [2024],
        "alternative_names": ["Swiss women case", "Senior women climate case"]
    }
}
```

### 3.3 Citation Signal Analysis

```python
CITATION_SIGNALS = {
    "foreign_indicators": [
        "foreign court", "international court", "comparative", "persuasive authority",
        "non-binding", "other jurisdictions", "transnational", "cross-border",
        "from abroad", "overseas decision", "external precedent", "global perspective"
    ],
    
    "domestic_indicators": [
        "this court", "we held", "our precedent", "binding authority", "controlling",
        "this circuit", "our jurisdiction", "previously decided", "well-established",
        "this tribunal", "domestic law", "national precedent"
    ],
    
    "neutral_signals": [
        "see", "cf.", "compare", "but see", "accord", "contra", "see also",
        "see generally", "citing", "quoting", "referencing"
    ]
}

def analyze_citation_signals(context_before, context_after):
    """
    Analyze contextual signals to help identify if citation is foreign.
    
    Returns: {'foreign_score': float, 'domestic_score': float, 'signals_found': list}
    """
    foreign_score = 0
    domestic_score = 0
    signals_found = []
    
    combined_context = f"{context_before} {context_after}".lower()
    
    for signal in CITATION_SIGNALS['foreign_indicators']:
        if signal in combined_context:
            foreign_score += 1
            signals_found.append(('foreign', signal))
    
    for signal in CITATION_SIGNALS['domestic_indicators']:
        if signal in combined_context:
            domestic_score += 1
            signals_found.append(('domestic', signal))
    
    return {
        'foreign_score': foreign_score,
        'domestic_score': domestic_score,
        'signals_found': signals_found
    }
```

### 3.4 Jurisdiction Aliases

```python
JURISDICTION_ALIASES = {
    "Netherlands": ["Holland", "Dutch", "The Hague", "Nederland"],
    "United Kingdom": ["UK", "Britain", "English", "Welsh", "Scottish", "Northern Ireland"],
    "United States": ["US", "USA", "American", "Federal"],
    "European Union": ["EU", "Community", "European", "Brussels", "Luxembourg"],
    "Germany": ["German", "Federal Republic", "Deutschland", "Deutsch"],
    "France": ["French", "République française"],
    "Brazil": ["Brazilian", "Brasil"],
    "Canada": ["Canadian", "Dominion"],
    "Australia": ["Australian", "Commonwealth of Australia"],
    "India": ["Indian", "Bharat"],
    "South Africa": ["South African", "RSA"],
    "Norway": ["Norwegian", "Norge", "Noreg"],
    "Ireland": ["Irish", "Éire", "Republic of Ireland"]
}

def normalize_jurisdiction(jurisdiction_string):
    """Convert various jurisdiction names to standard country name."""
    jurisdiction_lower = jurisdiction_string.lower()
    
    for country, aliases in JURISDICTION_ALIASES.items():
        if country.lower() == jurisdiction_lower:
            return country
        for alias in aliases:
            if alias.lower() in jurisdiction_lower:
                return country
    
    return jurisdiction_string  # Return original if no match
```

### 3.5 Three-Tier Origin Identification

```python
def identify_origin_tier1(case_ref):
    """
    Tier 1: Database lookup (FREE).
    
    INPUT: case_ref dictionary from Phase 2
    OUTPUT: {'country': str, 'confidence': float, 'method': 'database'}
    """
    raw_text = case_ref['raw_text'].lower()
    
    # Check court names
    for court_name, court_info in KNOWN_FOREIGN_COURTS.items():
        if court_name.lower() in raw_text:
            return {
                'country': court_info['country'],
                'confidence': 1.0,
                'method': 'court_database',
                'tribunal_name': court_name if court_info['country'] == 'International' else None
            }
    
    # Check landmark cases
    for case_name, case_info in LANDMARK_CLIMATE_CASES.items():
        if case_name.lower() in raw_text:
            return {
                'country': case_info['country'],
                'confidence': 0.95,
                'method': 'landmark_database',
                'tribunal_name': None
            }
        # Check alternative names
        for alt_name in case_info.get('alternative_names', []):
            if alt_name.lower() in raw_text:
                return {
                    'country': case_info['country'],
                    'confidence': 0.9,
                    'method': 'landmark_database_alt',
                    'tribunal_name': None
                }
    
    # No match found
    return None

def identify_origin_tier2_sonnet(case_ref, context_analysis=None):
    """
    Tier 2: Sonnet LLM analysis.
    
    Includes signal analysis for better accuracy.
    """
    # Include signal analysis if available
    signal_info = ""
    if context_analysis:
        signal_info = f"""
Context signals analysis:
- Foreign indicators found: {context_analysis['foreign_score']}
- Domestic indicators found: {context_analysis['domestic_score']}
- Specific signals: {context_analysis['signals_found']}
"""
    
    prompt = f"""Identify the country of origin for this case law reference.

Case reference: {case_ref['raw_text']}
Context before: {case_ref.get('context_before', '')}
Context after: {case_ref.get('context_after', '')}
{signal_info}

Provide ONLY a JSON response:
{{
    "country": "country name or International",
    "confidence": 0.0-1.0,
    "tribunal_name": "name if international tribunal",
    "reasoning": "brief explanation",
    "needs_web_search": true/false
}}"""
    
    # Call Sonnet API
    # ... API call implementation ...
    
def identify_origin_tier3_web(case_ref):
    """
    Tier 3: Web search verification.
    
    For cases with confidence < 0.7 or when requested by Tier 2.
    """
    search_query = f"{case_ref['case_name']} court case jurisdiction country"
    
    # Web search implementation
    # ... web search call ...
```

---

## ⚖️ PHASE 4: CLASSIFICATION

### 4.1 Enhanced Classification Logic

```python
def classify_citation_type(source_jurisdiction, case_law_origin, tribunal_name=None):
    """
    Classify citation based on jurisdiction comparison.
    
    INPUT:
        - source_jurisdiction: Country of the citing court
        - case_law_origin: Country of the cited case
        - tribunal_name: Name of tribunal if international
    
    OUTPUT: 'Domestic' | 'Foreign' | 'International' | 'Foreign International'
    """
    
    # Normalize jurisdictions
    source_normalized = normalize_jurisdiction(source_jurisdiction)
    origin_normalized = normalize_jurisdiction(case_law_origin)
    
    # Check if same country
    if source_normalized == origin_normalized:
        return "Domestic Citation"
    
    # Check if international
    if origin_normalized == "International":
        # Check if has jurisdiction over source
        if tribunal_name and has_jurisdiction_over(tribunal_name, source_normalized):
            return "International Citation"
        else:
            return "Foreign International Citation"
    
    # Different countries = foreign
    return "Foreign Citation"

def has_jurisdiction_over(tribunal_name, country):
    """
    Check if international tribunal has jurisdiction over country.
    Uses existing binding courts logic from config.py.
    """
    from config import get_binding_courts
    binding_courts = get_binding_courts(country)
    return tribunal_name in binding_courts
```

---

## 💾 DATABASE SCHEMA

### Create Table SQL

```sql
CREATE TABLE citation_extraction_phased (
    -- Primary Key
    extraction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    
    -- PHASE 1: Source Jurisdiction
    source_jurisdiction VARCHAR(100),
    source_geographies TEXT,
    source_region VARCHAR(50),
    
    -- PHASE 2: Extraction
    case_name_extracted TEXT NOT NULL,
    raw_citation_text TEXT NOT NULL,
    citation_context_before TEXT,
    citation_context_after TEXT,
    citation_section TEXT,
    citation_location VARCHAR(50), -- main_text|footnote|dissent|concurrence
    extraction_format VARCHAR(50),
    extraction_confidence DECIMAL(3,2),
    
    -- PHASE 3: Origin Identification
    case_law_origin VARCHAR(100),
    origin_confidence DECIMAL(3,2),
    origin_reasoning TEXT,
    origin_identification_method VARCHAR(50),
    web_search_used BOOLEAN DEFAULT FALSE,
    signal_analysis JSONB,
    
    -- PHASE 4: Classification
    citation_type VARCHAR(50),
    
    -- Metadata
    phase_2_model VARCHAR(50) DEFAULT 'claude-haiku-4.5',
    phase_3_model VARCHAR(50),
    phase_4_model VARCHAR(50) DEFAULT 'claude-haiku-4.5',
    processing_time_seconds DECIMAL(10,2),
    api_calls_used INTEGER,
    
    -- Quality Control
    requires_manual_review BOOLEAN DEFAULT FALSE,
    manual_review_reason TEXT,
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_citation_phased_document ON citation_extraction_phased(document_id);
CREATE INDEX idx_citation_phased_type ON citation_extraction_phased(citation_type);
CREATE INDEX idx_citation_phased_origin ON citation_extraction_phased(case_law_origin);
CREATE INDEX idx_citation_phased_review ON citation_extraction_phased(requires_manual_review);
CREATE INDEX idx_citation_phased_source ON citation_extraction_phased(source_jurisdiction);
```

---

## 🧪 TESTING PROTOCOL

### Control Group Documents

1. **Known Foreign Citations (5 documents)**
   - Thomson v Minister (NZ) - cites Urgenda
   - Plan B Earth v PM (UK) - cites Massachusetts v EPA
   - Mathur v Ontario (Canada) - references international cases
   - Friends of Irish Environment - cites European cases
   - Greenpeace Nordic v Norway - references comparative law

2. **Mixed Citations (3 documents)**
   - Documents with both domestic and foreign citations
   - Test discrimination accuracy

3. **No Foreign Citations (2 documents)**
   - Pure domestic case law
   - Test false positive rate

### Success Metrics

```python
def evaluate_performance(control_group_results):
    """
    Calculate performance metrics.
    
    Target metrics:
    - Recall: ≥ 75% (find most foreign citations)
    - Precision: ≥ 85% (accurate classification)
    - F1 Score: ≥ 0.80
    """
    metrics = {
        'total_foreign_citations_expected': 0,
        'total_foreign_citations_found': 0,
        'true_positives': 0,
        'false_positives': 0,
        'false_negatives': 0,
        
        'by_phase': {
            'phase2_extraction_rate': 0,
            'phase3_identification_rate': 0,
            'phase4_classification_accuracy': 0
        },
        
        'by_format': {
            'traditional': {'found': 0, 'missed': 0},
            'narrative': {'found': 0, 'missed': 0},
            'shorthand': {'found': 0, 'missed': 0},
            # ... other formats
        }
    }
    
    # Calculate metrics
    # ... implementation ...
    
    return metrics
```

---

## ⚡ OPTIMIZATION FEATURES

### 1. Citation Cache

```python
# Global cache for repeated citations
CITATION_ORIGIN_CACHE = {}

def get_cached_origin(case_name):
    """Check cache before calling expensive operations."""
    cache_key = case_name.lower().strip()
    if cache_key in CITATION_ORIGIN_CACHE:
        return CITATION_ORIGIN_CACHE[cache_key]
    return None

def cache_origin(case_name, origin_data):
    """Cache successful origin identifications."""
    cache_key = case_name.lower().strip()
    CITATION_ORIGIN_CACHE[cache_key] = origin_data
```

### 2. Batch Processing

```python
def batch_process_phase3_tier2(uncertain_cases):
    """
    Process multiple uncertain cases in single Sonnet call.
    More cost-effective than individual calls.
    """
    if len(uncertain_cases) <= 3:
        # Process individually if few cases
        return [identify_origin_tier2_sonnet(case) for case in uncertain_cases]
    
    # Batch prompt for multiple cases
    batch_prompt = "Identify origins for these cases:\n"
    for i, case in enumerate(uncertain_cases, 1):
        batch_prompt += f"\n{i}. {case['raw_text']}"
    
    # Single API call for all cases
    # ... implementation ...
```

### 3. Cross-Reference Validation

```python
def validate_cross_references(document_citations):
    """
    If Document A cites Case X which cites Case Y,
    verify Case Y is also captured.
    """
    missing_cross_refs = []
    
    for citation in document_citations:
        # Check if cited case should have its own citations
        if citation['case_name'] in LANDMARK_CLIMATE_CASES:
            # Known case - check if its citations are captured
            # ... implementation ...
            pass
    
    return missing_cross_refs
```

### 4. Deduplication

```python
def deduplicate_citations(citations):
    """
    Same case may be cited differently in same document.
    Normalize and merge duplicate citations.
    """
    normalized_citations = {}
    
    for citation in citations:
        # Create normalized key
        key = normalize_citation_key(citation['case_name'])
        
        if key not in normalized_citations:
            normalized_citations[key] = citation
        else:
            # Merge information from duplicate
            existing = normalized_citations[key]
            existing['raw_citation_text'] += f"; {citation['raw_citation_text']}"
            existing['confidence'] = max(existing['confidence'], citation['confidence'])
    
    return list(normalized_citations.values())
```

---

## 📊 IMPLEMENTATION TIMELINE

### Week 1: Foundation (Days 1-7)

**Day 1: Database & Phase 1**
- [ ] Create database schema
- [ ] Implement Phase 1 functions
- [ ] Test jurisdiction extraction

**Days 2-3: Dictionaries & Lookups**
- [ ] Build KNOWN_FOREIGN_COURTS
- [ ] Build LANDMARK_CLIMATE_CASES
- [ ] Implement Tier 1 lookup functions
- [ ] Add jurisdiction aliases

**Days 4-5: Phase 2 Extraction**
- [ ] Create enhanced extraction prompt
- [ ] Implement all citation format patterns
- [ ] Add context capture (before/after)
- [ ] Test on control documents

**Days 6-7: Phase 3 Origin**
- [ ] Implement 3-tier identification
- [ ] Add signal analysis
- [ ] Integrate web search
- [ ] Test accuracy on known cases

### Week 2: Integration (Days 8-14)

**Days 8-9: Phase 4 & Integration**
- [ ] Implement classification logic
- [ ] Integrate all phases
- [ ] Add caching and optimization
- [ ] Run control group tests

**Days 10-11: Refinement**
- [ ] Analyze errors from control group
- [ ] Adjust confidence thresholds
- [ ] Expand dictionaries based on findings
- [ ] Retest and validate

**Days 12-14: Deployment**
- [ ] Deploy on trial batch
- [ ] Monitor performance
- [ ] Generate reports
- [ ] Flag items for manual review

---

## 🚨 CRITICAL REMINDERS

1. **Phase 2 extracts EVERYTHING** - No filtering for foreign/domestic
2. **Use existing get_binding_courts()** for international jurisdiction
3. **Test incrementally** - Each phase independently before integration
4. **Cache repeated lookups** to reduce API costs
5. **Confidence < 0.7** triggers manual review
6. **Include administrative tribunals** in extraction
7. **Capture extended context** (2-3 sentences before/after)
8. **Normalize jurisdictions** before comparison
9. **Document everything** for thesis methodology
10. **Prioritize recall over precision** in Phase 2

---

## 📁 FILE STRUCTURE

```
/home/gusrodgs/Gus/cienciaDeDados/phdMutley/
├── scripts/
│   └── phase2/
│       ├── extract_citations_v4.py (current version)
│       └── extract_citations_v5_phased.py (NEW - to create)
├── config.py (existing - contains get_binding_courts)
├── logs/
│   └── citation_extraction_v5.log
└── data/
    └── control_group/
        └── known_foreign_citations.xlsx
```

---

## ✅ READY TO IMPLEMENT

This document contains:
- Complete 4-phase architecture
- All enhanced dictionaries and databases
- Ready-to-use code snippets
- Database schema
- Testing protocol
- Implementation timeline

**Start implementation with:** Database schema creation and Phase 1 functions

---

**Document Version:** 2.0 (Enhanced)  
**Created:** November 22, 2025  
**Status:** READY FOR IMPLEMENTATION  
**Author:** Assistant with Gustavo Rodrigues
