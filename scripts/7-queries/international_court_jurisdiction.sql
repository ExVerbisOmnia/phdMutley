-- ============================================================================
-- INTERNATIONAL COURT JURISDICTION SUPPORT TABLE
-- Climate Litigation PhD Research Project
-- 
-- Author: Gustavo (with Claude assistance)
-- Date: November 28, 2025
-- Purpose: Enable sixfold citation classification by mapping international 
--          courts to their member states
--
-- Execute with: psql -d climate_litigation -f international_court_jurisdiction.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- DROP TABLE IF EXISTS (for re-running)
-- ============================================================================

DROP TABLE IF EXISTS international_court_jurisdiction CASCADE;

-- ============================================================================
-- CREATE SUPPORT TABLE
-- ============================================================================

CREATE TABLE international_court_jurisdiction (
    court_id SERIAL PRIMARY KEY,
    
    -- Court identification
    court_name VARCHAR(200) NOT NULL,
    court_abbreviation VARCHAR(50) NOT NULL,
    court_system VARCHAR(100),
    
    -- Jurisdiction type
    jurisdiction_type VARCHAR(50),  -- 'Regional', 'Global', 'Supranational'
    
    -- Member jurisdictions (as they appear in source_jurisdiction/case_law_origin)
    -- Using TEXT[] array for flexible matching
    member_jurisdictions TEXT[],
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Comments
    notes TEXT
);

-- Add index for faster lookups
CREATE INDEX idx_court_abbreviation ON international_court_jurisdiction(court_abbreviation);
CREATE INDEX idx_court_name ON international_court_jurisdiction(court_name);

-- ============================================================================
-- INSERT INTERNATIONAL COURTS DATA
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. EUROPEAN COURT OF HUMAN RIGHTS (ECtHR) - Council of Europe
-- 46 member states
-- ---------------------------------------------------------------------------
INSERT INTO international_court_jurisdiction (
    court_name, 
    court_abbreviation, 
    court_system, 
    jurisdiction_type, 
    member_jurisdictions,
    notes
) VALUES (
    'European Court of Human Rights',
    'ECtHR',
    'Council of Europe',
    'Regional',
    ARRAY[
        -- As they appear in the database
        'Albania', 'Andorra', 'Armenia', 'Austria', 'Azerbaijan',
        'Belgium', 'Bosnia and Herzegovina', 'Bulgaria', 'Croatia', 'Cyprus',
        'Czech Republic', 'Czechia', 'Denmark', 'Estonia', 'Finland',
        'France', 'Georgia', 'Germany', 'Greece', 'Hungary',
        'Iceland', 'Ireland', 'Italy', 'Latvia', 'Liechtenstein',
        'Lithuania', 'Luxembourg', 'Malta', 'Moldova', 'Monaco',
        'Montenegro', 'Netherlands', 'North Macedonia', 'Norway', 'Poland',
        'Portugal', 'Romania', 'San Marino', 'Serbia', 'Slovakia',
        'Slovenia', 'Spain', 'Sweden', 'Switzerland', 'Turkey', 'Türkiye',
        'Ukraine', 'United Kingdom', 'England', 'Wales', 'Scotland', 
        'Northern Ireland', 'England and Wales'
    ],
    '46 Council of Europe member states. Russia expelled in March 2022.'
);

-- Also add alternate name patterns for ECtHR
INSERT INTO international_court_jurisdiction (
    court_name, 
    court_abbreviation, 
    court_system, 
    jurisdiction_type, 
    member_jurisdictions,
    notes
) VALUES (
    'Council of Europe',
    'CoE',
    'Council of Europe',
    'Regional',
    ARRAY[
        'Albania', 'Andorra', 'Armenia', 'Austria', 'Azerbaijan',
        'Belgium', 'Bosnia and Herzegovina', 'Bulgaria', 'Croatia', 'Cyprus',
        'Czech Republic', 'Czechia', 'Denmark', 'Estonia', 'Finland',
        'France', 'Georgia', 'Germany', 'Greece', 'Hungary',
        'Iceland', 'Ireland', 'Italy', 'Latvia', 'Liechtenstein',
        'Lithuania', 'Luxembourg', 'Malta', 'Moldova', 'Monaco',
        'Montenegro', 'Netherlands', 'North Macedonia', 'Norway', 'Poland',
        'Portugal', 'Romania', 'San Marino', 'Serbia', 'Slovakia',
        'Slovenia', 'Spain', 'Sweden', 'Switzerland', 'Turkey', 'Türkiye',
        'Ukraine', 'United Kingdom', 'England', 'Wales', 'Scotland', 
        'Northern Ireland', 'England and Wales'
    ],
    'Same membership as ECtHR - Council of Europe system'
);

-- ---------------------------------------------------------------------------
-- 2. COURT OF JUSTICE OF THE EUROPEAN UNION (CJEU)
-- 27 member states
-- ---------------------------------------------------------------------------
INSERT INTO international_court_jurisdiction (
    court_name, 
    court_abbreviation, 
    court_system, 
    jurisdiction_type, 
    member_jurisdictions,
    notes
) VALUES (
    'Court of Justice of the European Union',
    'CJEU',
    'European Union',
    'Supranational',
    ARRAY[
        'Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus',
        'Czech Republic', 'Czechia', 'Denmark', 'Estonia', 'Finland',
        'France', 'Germany', 'Greece', 'Hungary', 'Ireland',
        'Italy', 'Latvia', 'Lithuania', 'Luxembourg', 'Malta',
        'Netherlands', 'Poland', 'Portugal', 'Romania', 'Slovakia',
        'Slovenia', 'Spain', 'Sweden'
    ],
    '27 EU member states. UK left in 2020.'
);

-- Alternate abbreviation ECJ
INSERT INTO international_court_jurisdiction (
    court_name, 
    court_abbreviation, 
    court_system, 
    jurisdiction_type, 
    member_jurisdictions,
    notes
) VALUES (
    'European Court of Justice',
    'ECJ',
    'European Union',
    'Supranational',
    ARRAY[
        'Austria', 'Belgium', 'Bulgaria', 'Croatia', 'Cyprus',
        'Czech Republic', 'Czechia', 'Denmark', 'Estonia', 'Finland',
        'France', 'Germany', 'Greece', 'Hungary', 'Ireland',
        'Italy', 'Latvia', 'Lithuania', 'Luxembourg', 'Malta',
        'Netherlands', 'Poland', 'Portugal', 'Romania', 'Slovakia',
        'Slovenia', 'Spain', 'Sweden'
    ],
    'Alternate name for CJEU'
);

-- ---------------------------------------------------------------------------
-- 3. INTER-AMERICAN COURT OF HUMAN RIGHTS (IACtHR)
-- 20 states that accepted contentious jurisdiction
-- ---------------------------------------------------------------------------
INSERT INTO international_court_jurisdiction (
    court_name, 
    court_abbreviation, 
    court_system, 
    jurisdiction_type, 
    member_jurisdictions,
    notes
) VALUES (
    'Inter-American Court of Human Rights',
    'IACtHR',
    'Organization of American States',
    'Regional',
    ARRAY[
        'Argentina', 'Barbados', 'Bolivia', 'Brazil', 'Chile',
        'Colombia', 'Costa Rica', 'Dominican Republic', 'Ecuador', 'El Salvador',
        'Guatemala', 'Haiti', 'Honduras', 'Mexico', 'Nicaragua',
        'Panama', 'Paraguay', 'Peru', 'Suriname', 'Uruguay'
    ],
    '20 OAS states that accepted contentious jurisdiction. Trinidad/Tobago and Venezuela withdrew.'
);

-- Also for Inter-American System references
INSERT INTO international_court_jurisdiction (
    court_name, 
    court_abbreviation, 
    court_system, 
    jurisdiction_type, 
    member_jurisdictions,
    notes
) VALUES (
    'Inter-American Human Rights System',
    'IAHRS',
    'Organization of American States',
    'Regional',
    ARRAY[
        'Argentina', 'Barbados', 'Bolivia', 'Brazil', 'Chile',
        'Colombia', 'Costa Rica', 'Dominican Republic', 'Ecuador', 'El Salvador',
        'Guatemala', 'Haiti', 'Honduras', 'Mexico', 'Nicaragua',
        'Panama', 'Paraguay', 'Peru', 'Suriname', 'Uruguay'
    ],
    'Same as IACtHR - Inter-American System'
);

-- ---------------------------------------------------------------------------
-- 4. AFRICAN COURT ON HUMAN AND PEOPLES' RIGHTS (ACtHPR)
-- 34 states that ratified the protocol
-- ---------------------------------------------------------------------------
INSERT INTO international_court_jurisdiction (
    court_name, 
    court_abbreviation, 
    court_system, 
    jurisdiction_type, 
    member_jurisdictions,
    notes
) VALUES (
    'African Court on Human and Peoples Rights',
    'ACtHPR',
    'African Union',
    'Regional',
    ARRAY[
        'Algeria', 'Benin', 'Burkina Faso', 'Burundi', 'Cameroon',
        'Chad', 'Comoros', 'Congo', 'Cote d''Ivoire', 'Gabon',
        'Gambia', 'Ghana', 'Guinea-Bissau', 'Kenya', 'Lesotho',
        'Libya', 'Madagascar', 'Malawi', 'Mali', 'Mauritania',
        'Mauritius', 'Mozambique', 'Niger', 'Nigeria', 'Rwanda',
        'Sahrawi Arab Democratic Republic', 'Senegal', 'South Africa', 
        'Tanzania', 'Togo', 'Tunisia', 'Uganda', 'Zambia'
    ],
    '34 AU states that ratified the Protocol. As of August 2024.'
);

-- ---------------------------------------------------------------------------
-- 5. INTERNATIONAL COURT OF JUSTICE (ICJ) - Universal jurisdiction
-- All UN member states (193) - represented as wildcard
-- ---------------------------------------------------------------------------
INSERT INTO international_court_jurisdiction (
    court_name, 
    court_abbreviation, 
    court_system, 
    jurisdiction_type, 
    member_jurisdictions,
    notes
) VALUES (
    'International Court of Justice',
    'ICJ',
    'United Nations',
    'Global',
    ARRAY['*ALL*'],  -- Special marker for universal jurisdiction
    'All 193 UN member states. Universal jurisdiction for inter-state disputes.'
);

-- ---------------------------------------------------------------------------
-- 6. WORLD TRADE ORGANIZATION (WTO) Dispute Settlement
-- 164 member states - represented as wildcard
-- ---------------------------------------------------------------------------
INSERT INTO international_court_jurisdiction (
    court_name, 
    court_abbreviation, 
    court_system, 
    jurisdiction_type, 
    member_jurisdictions,
    notes
) VALUES (
    'World Trade Organization',
    'WTO',
    'World Trade Organization',
    'Global',
    ARRAY['*ALL*'],  -- Special marker for near-universal jurisdiction
    '164 WTO members. Near-universal coverage for trade disputes.'
);

-- ---------------------------------------------------------------------------
-- 7. INTERNATIONAL CENTRE FOR SETTLEMENT OF INVESTMENT DISPUTES (ICSID)
-- 165 contracting states
-- ---------------------------------------------------------------------------
INSERT INTO international_court_jurisdiction (
    court_name, 
    court_abbreviation, 
    court_system, 
    jurisdiction_type, 
    member_jurisdictions,
    notes
) VALUES (
    'International Centre for Settlement of Investment Disputes',
    'ICSID',
    'World Bank Group',
    'Global',
    ARRAY['*ALL*'],  -- Near-universal
    '165 contracting states. Investment arbitration.'
);

-- ---------------------------------------------------------------------------
-- 8. PERMANENT COURT OF ARBITRATION (PCA)
-- ---------------------------------------------------------------------------
INSERT INTO international_court_jurisdiction (
    court_name, 
    court_abbreviation, 
    court_system, 
    jurisdiction_type, 
    member_jurisdictions,
    notes
) VALUES (
    'Permanent Court of Arbitration',
    'PCA',
    'International Arbitration',
    'Global',
    ARRAY['*ALL*'],  -- Available to all states
    'Available to all states for international arbitration.'
);

-- ---------------------------------------------------------------------------
-- 9. ANDEAN TRIBUNAL OF JUSTICE
-- 4 member states
-- ---------------------------------------------------------------------------
INSERT INTO international_court_jurisdiction (
    court_name, 
    court_abbreviation, 
    court_system, 
    jurisdiction_type, 
    member_jurisdictions,
    notes
) VALUES (
    'Andean Tribunal of Justice',
    'ATJ',
    'Andean Community',
    'Regional',
    ARRAY['Bolivia', 'Colombia', 'Ecuador', 'Peru'],
    'Court of the Andean Community. 4 member states.'
);

-- ---------------------------------------------------------------------------
-- 10. EFTA COURT
-- 3 EEA/EFTA states (not EU members)
-- ---------------------------------------------------------------------------
INSERT INTO international_court_jurisdiction (
    court_name, 
    court_abbreviation, 
    court_system, 
    jurisdiction_type, 
    member_jurisdictions,
    notes
) VALUES (
    'EFTA Court',
    'EFTA',
    'European Free Trade Association',
    'Regional',
    ARRAY['Iceland', 'Liechtenstein', 'Norway'],
    'EEA/EFTA states. Switzerland is EFTA but not subject to EFTA Court.'
);

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

\echo ''
\echo '============================================================'
\echo 'VERIFICATION: International Court Jurisdiction Table'
\echo '============================================================'

\echo ''
\echo 'Courts loaded:'
SELECT court_abbreviation, court_name, court_system, jurisdiction_type, 
       array_length(member_jurisdictions, 1) as member_count
FROM international_court_jurisdiction
ORDER BY court_system, court_name;

\echo ''
\echo 'Sample: ECtHR member states:'
SELECT unnest(member_jurisdictions) as member_state
FROM international_court_jurisdiction
WHERE court_abbreviation = 'ECtHR'
ORDER BY member_state;

\echo ''
\echo 'Sample: IACtHR member states:'
SELECT unnest(member_jurisdictions) as member_state
FROM international_court_jurisdiction
WHERE court_abbreviation = 'IACtHR'
ORDER BY member_state;

-- ============================================================================
-- COMMIT
-- ============================================================================

COMMIT;

\echo ''
\echo '============================================================'
\echo '✓ International Court Jurisdiction table created successfully!'
\echo '============================================================'
\echo ''
