# config.py
"""
Central Configuration for phdMutley Project
===========================================
Centralizes paths, database connections, constants, and jurisdiction logic.

VERSION: 3.3 - Trial Batch Support
- Added TRIAL_BATCH_CONFIG for filtering specific documents
- Preserved TEST_CONFIG for limiting row counts
- Added CLASSIFICATION_MODEL for Sonnet-based classification
- Preserved Haiku 4.5 for citation extraction
- Added BINDING_JURISDICTIONS map
- Added get_binding_courts helper
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from uuid import uuid5, NAMESPACE_DNS

# Load environment variables
load_dotenv()

# Base Paths
PROJECT_ROOT = Path('/home/gusrodgs/Gus/cienciaDeDados/phdMutley')
PDF_DOWNLOAD_DIR = PROJECT_ROOT / 'pdfs/downloaded'
LOGS_DIR = PROJECT_ROOT / 'logs'
DATABASE_FILE = PROJECT_ROOT / 'baseCompleta.xlsx'

# Create directories immediately
PDF_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Database Configuration
DB_CONFIG = {
    'drivername': 'postgresql+psycopg2',
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'climate_litigation'),
    'username': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
}

# UUID Generation
UUID_NAMESPACE = uuid5(NAMESPACE_DNS, 'climatecasechart.com.phdmutley')

# --- Resource Calculation ---
available_cpus = os.cpu_count() or 2
safe_worker_count = max(1, int(available_cpus * 0.5))

# --- JURISDICTION MAPPING ---
# Maps countries to their binding international human rights courts.
# Used to distinguish "International" (binding) from "Foreign International" (persuasive).

BINDING_JURISDICTIONS = {
    # --- Inter-American Court of Human Rights (IACtHR) ---
    'IACtHR': [
        'Argentina', 'Barbados', 'Bolivia', 'Brazil', 'Chile', 'Colombia', 'Ecuador', 
        'Paraguay', 'Peru', 'Suriname', 'Uruguay', 'Costa Rica', 'El Salvador', 
        'Guatemala', 'Honduras', 'Nicaragua', 'Panama', 'Mexico', 'Haiti', 
        'Dominican Republic'
    ],

    # --- European Court of Human Rights (ECtHR) ---
    'ECtHR': [
        'Albania', 'Germany', 'Andorra', 'Armenia', 'Austria', 'Azerbaijan', 'Belgium', 
        'Bosnia and Herzegovina', 'Bulgaria', 'Cyprus', 'Croatia', 'Denmark', 'Slovakia', 
        'Slovenia', 'Spain', 'Estonia', 'Finland', 'France', 'Georgia', 'Greece', 
        'Hungary', 'Ireland', 'Iceland', 'Italy', 'Latvia', 'Liechtenstein', 'Lithuania', 
        'Luxembourg', 'North Macedonia', 'Malta', 'Moldova', 'Monaco', 'Montenegro', 
        'Norway', 'Netherlands', 'Poland', 'Portugal', 'United Kingdom', 'Czech Republic', 
        'Romania', 'San Marino', 'Serbia', 'Sweden', 'Switzerland', 'Turkey', 'Ukraine'
    ],

    # --- African Court on Human and Peoples' Rights (ACHPR) ---
    'ACHPR': [
        'Algeria', 'Benin', 'Burkina Faso', 'Burundi', 'Cameroon', 'Chad', 'Comoros', 
        'Congo', 'Ivory Coast', 'Cote d\'Ivoire', 'Gabon', 'Gambia', 'Ghana', 
        'Guinea-Bissau', 'Kenya', 'Lesotho', 'Libya', 'Malawi', 'Mali', 'Mauritania', 
        'Mozambique', 'Niger', 'Nigeria', 'Rwanda', 'Western Sahara', 'Senegal', 
        'South Africa', 'Tanzania', 'Togo', 'Tunisia', 'Uganda', 'Zambia', 'Zimbabwe'
    ]
}

# Global courts applicable to essentially everyone for the purpose of this study
GLOBAL_COURTS = [
    'International Court of Justice', 'ICJ', 
    'International Tribunal for the Law of the Sea', 'ITLOS'
]

def get_binding_courts(country):
    """
    Returns a string list of binding international courts for a given country.
    """
    if not country:
        return ", ".join(GLOBAL_COURTS)
        
    binding = list(GLOBAL_COURTS) # Start with global courts
    
    # check IACtHR
    if country in BINDING_JURISDICTIONS['IACtHR']:
        binding.extend(['Inter-American Court of Human Rights', 'IACtHR', 'Corte IDH'])
        
    # check ECtHR
    if country in BINDING_JURISDICTIONS['ECtHR']:
        binding.extend(['European Court of Human Rights', 'ECHR', 'ECtHR', 'CEDH'])
        
    # check ACHPR
    if country in BINDING_JURISDICTIONS['ACHPR']:
        binding.extend(['African Court on Human and Peoples\' Rights', 'ACHPR', 'Corte Africana'])
        
    return ", ".join(set(binding))

# Application Settings
CONFIG = {
    # Download Settings
    'CONCURRENT_DOWNLOADS': 10,
    'REQUEST_TIMEOUT': 30,
    
    # Extraction Settings
    'MAX_WORKERS': safe_worker_count,
    'SCANNED_PDF_THRESHOLD': 100,
    
    # LLM / Citation Settings
    'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
    'ANTHROPIC_MODEL': 'claude-haiku-4-5-20251001',  # Haiku for citation extraction
    'CLASSIFICATION_MODEL': 'claude-sonnet-4-5-20250929',  # Sonnet for classification
    
    # Model Specifications
    'MODEL_CONTEXT_WINDOW': 200000,
    'MODEL_MAX_OUTPUT': 8192,
    'SAFE_TOKEN_THRESHOLD': 190000,
    
    # Processing Settings
    'CLASSIFICATION_TEXT_LIMIT': 3000,
    
    # Quality Thresholds
    'MIN_CONFIDENCE': 0.3,
}

# Centralized Test Configuration
# Used for development testing with limited row counts
TEST_CONFIG = {
    'ENABLED': False,          # Master switch for all scripts
    'LIMIT': 50,              # Number of rows/files/docs to process in test mode
    'STRATEGY': 'first',      # Options: 'first', 'random'
}

# Trial Batch Configuration
# Filters processing to only documents marked as trial batch in the database
# This is different from TEST_CONFIG - trial batch targets specific documents
# marked in the Excel file, while TEST_CONFIG limits to first N rows
TRIAL_BATCH_CONFIG = {
    'ENABLED': True,                    # Master switch for trial batch filtering
    'COLUMN_NAME': 'Trial batch',       # Name of the column in Excel/database
    'TRUE_VALUES': [True, 'TRUE', 'True', 'true', 1, '1', 'yes', 'Yes', 'YES']  # Values indicating trial batch membership
}
