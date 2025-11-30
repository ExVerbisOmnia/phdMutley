#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
SIXFOLD CITATION CLASSIFICATION - ANALYSIS ENGINE
============================================================================

Climate Litigation PhD Research Project
Author: Gustavo (with Claude assistance)
Date: November 28, 2025

Purpose:
--------
This module serves as the backend analysis engine for the sixfold citation
classification system. It performs the following functions:

1. Creates and populates the `first_analysis` table in PostgreSQL
2. Executes all analytical queries from the SQL specification
3. Generates citation network data for visualization tools (JSON/CSV)
4. Creates aggregate tables for dashboards (JSON)
5. Provides an API-ready structure for frontend integration

Tech Stack:
-----------
- SQLAlchemy 2.0+ (ORM and Core)
- PostgreSQL 18 (via psycopg2)
- Pandas (data manipulation)
- JSON (external data storage)

Usage:
------
    # As a standalone script:
    python sixfold_analysis_engine.py
    
    # As a module (for API integration):
    from sixfold_analysis_engine import SixfoldAnalysisEngine
    engine = SixfoldAnalysisEngine()
    engine.run_full_analysis()

============================================================================
"""

import os
import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from dotenv import load_dotenv

# Load environment variables from project root
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(env_path)

# SQLAlchemy imports
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Float,
    Text, DateTime, Boolean, ForeignKey, Index, text, inspect,
    select, func, case, and_, or_, distinct, literal_column
)
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.exc import SQLAlchemyError

# Data manipulation
import pandas as pd

# =============================================================================
# CONFIGURATION
# =============================================================================

# Database connection string - adjust as needed for your environment
# Database connection string - adjust as needed for your environment
DB_USER = os.getenv('DB_USER', 'phdmutley')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'climate_litigation')

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Output directories for external data storage
OUTPUT_DIR = Path('./analysis_output')
NETWORK_DIR = OUTPUT_DIR / 'network_data'
DASHBOARD_DIR = OUTPUT_DIR / 'dashboard_data'

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('SixfoldAnalysisEngine')


# =============================================================================
# ENUMERATIONS - Sixfold Classification Types
# =============================================================================

class SixfoldType(Enum):
    """
    Enumeration of the six citation classification types.
    Each type represents a distinct pattern of transnational judicial dialogue.
    """
    FOREIGN = "Foreign Citation"                     # National → National
    INTERNATIONAL = "International Citation"          # National → Int'l (member)
    FOREIGN_INTERNATIONAL = "Foreign International Citation"  # National → Int'l (non-member)
    INTER_SYSTEM = "Inter-System Citation"           # Int'l → Int'l
    MEMBER_STATE = "Member-State Citation"           # Int'l → National (member)
    NON_MEMBER = "Non-Member Citation"               # Int'l → National (non-member)


class CitationDirection(Enum):
    """
    Enumeration of citation flow directions for categorization.
    """
    NATIONAL_TO_NATIONAL = "National → National"
    NATIONAL_TO_INTERNATIONAL = "National → International"
    INTERNATIONAL_TO_INTERNATIONAL = "International → International"
    INTERNATIONAL_TO_NATIONAL = "International → National"
    OTHER = "Other"


# =============================================================================
# GEOGRAPHIC DATA
# =============================================================================

JURISDICTION_COORDINATES = {
    # Global North
    "United Kingdom": {"lat": 55.3781, "lon": -3.4360},
    "UK": {"lat": 55.3781, "lon": -3.4360},
    "United States": {"lat": 37.0902, "lon": -95.7129},
    "USA": {"lat": 37.0902, "lon": -95.7129},
    "Canada": {"lat": 56.1304, "lon": -106.3468},
    "Australia": {"lat": -25.2744, "lon": 133.7751},
    "New Zealand": {"lat": -40.9006, "lon": 174.8860},
    "Ireland": {"lat": 53.1424, "lon": -7.6921},
    "Germany": {"lat": 51.1657, "lon": 10.4515},
    "France": {"lat": 46.2276, "lon": 2.2137},
    "Netherlands": {"lat": 52.1326, "lon": 5.2913},
    "Belgium": {"lat": 50.5039, "lon": 4.4699},
    "Switzerland": {"lat": 46.8182, "lon": 8.2275},
    "Norway": {"lat": 60.4720, "lon": 8.4689},
    "Sweden": {"lat": 60.1282, "lon": 18.6435},
    "Denmark": {"lat": 56.2639, "lon": 9.5018},
    "Finland": {"lat": 61.9241, "lon": 25.7482},
    "Italy": {"lat": 41.8719, "lon": 12.5674},
    "Spain": {"lat": 40.4637, "lon": -3.7492},
    "Portugal": {"lat": 39.3999, "lon": -8.2245},
    "Austria": {"lat": 47.5162, "lon": 14.5501},
    
    # Global South
    "Brazil": {"lat": -14.2350, "lon": -51.9253},
    "India": {"lat": 20.5937, "lon": 78.9629},
    "South Africa": {"lat": -30.5595, "lon": 22.9375},
    "Colombia": {"lat": 4.5709, "lon": -74.2973},
    "Argentina": {"lat": -38.4161, "lon": -63.6167},
    "Chile": {"lat": -35.6751, "lon": -71.5430},
    "Mexico": {"lat": 23.6345, "lon": -102.5528},
    "Philippines": {"lat": 12.8797, "lon": 121.7740},
    "Pakistan": {"lat": 30.3753, "lon": 69.3451},
    "Kenya": {"lat": -0.0236, "lon": 37.9062},
    "Nigeria": {"lat": 9.0820, "lon": 8.6753},
    "Bangladesh": {"lat": 23.6850, "lon": 90.3563},
    "Indonesia": {"lat": -0.7893, "lon": 113.9213},
    "Malaysia": {"lat": 4.2105, "lon": 101.9758},
    
    # International Courts (Approximate locations based on HQ)
    "ICJ": {"lat": 52.0866, "lon": 4.2955},  # The Hague
    "ECtHR": {"lat": 48.6000, "lon": 7.7500}, # Strasbourg
    "CJEU": {"lat": 49.6116, "lon": 6.1319},  # Luxembourg
    "IACtHR": {"lat": 9.9281, "lon": -84.0907}, # San Jose, Costa Rica
    "ECOWAS Court": {"lat": 9.0765, "lon": 7.3986}, # Abuja
    "EACJ": {"lat": -3.3731, "lon": 36.6830}, # Arusha
    "ITLOS": {"lat": 53.5511, "lon": 9.9937}, # Hamburg
    
    # Specific mappings from dataset
    "European Court of Human Rights (International Court)": {"lat": 48.6000, "lon": 7.7500},
    "International (Inter-American Court of Human Rights)": {"lat": 9.9281, "lon": -84.0907},
    "International (WTO)": {"lat": 46.2206, "lon": 6.1430}, # Geneva
    "International Tribunal": {"lat": 52.0866, "lon": 4.2955}, # Default to Hague
    "United Kingdom (England & Wales)": {"lat": 51.5074, "lon": -0.1278},
    "United Kingdom (Supreme Court)": {"lat": 51.5002, "lon": -0.1286},
    "United States (Supreme Court)": {"lat": 38.8905, "lon": -77.0044},
}


# =============================================================================
# DATA CLASSES - Structured Results
# =============================================================================

class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

@dataclass
class AnalysisResult:
    """
    Container for a single analysis query result.
    Provides metadata about the query and its results.
    """
    query_id: str           # Unique identifier (e.g., "1.1", "2.3")
    section: int            # Section number (0-8)
    category: str           # Category name (e.g., "Foreign Citation")
    description: str        # Human-readable description
    query_type: str         # Type: overview, flow_matrix, top_n, etc.
    data: List[Dict]        # Query results as list of dictionaries
    row_count: int          # Number of rows returned
    executed_at: datetime   # Timestamp of execution
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            **asdict(self),
            'executed_at': self.executed_at.isoformat()
        }


@dataclass
class NetworkEdge:
    """
    Represents a citation network edge for visualization.
    Source and target can be jurisdictions, tribunals, or cases.
    """
    source: str             # Source node (citing entity)
    target: str             # Target node (cited entity)
    source_type: str        # Node type: jurisdiction, tribunal, case
    target_type: str        # Node type: jurisdiction, tribunal, case
    source_region: str      # Global North, Global South, International
    target_region: str      # Global North, Global South, International
    weight: int             # Citation count
    sixfold_type: str       # Classification type
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON/CSV export."""
        return asdict(self)


@dataclass
class NodeAttributes:
    """
    Attributes for network visualization nodes.
    """
    node_id: str            # Unique identifier
    node_type: str          # jurisdiction, tribunal, case
    label: str              # Display label
    region: str             # Global North, Global South, International
    in_degree: int          # Number of incoming citations
    out_degree: int         # Number of outgoing citations
    total_degree: int       # Total citations
    lat: Optional[float] = None  # Latitude
    lon: Optional[float] = None  # Longitude
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON export."""
        return asdict(self)


# =============================================================================
# MAIN ENGINE CLASS
# =============================================================================

class SixfoldAnalysisEngine:
    """
    Main analysis engine for sixfold citation classification.
    
    This class orchestrates all analysis operations:
    - Database table management
    - Query execution
    - Network data generation
    - Dashboard aggregate creation
    
    Designed to serve as a backend for frontend applications.
    """
    
    def __init__(self, database_url: str = DATABASE_URL):
        """
        Initialize the analysis engine.
        
        Parameters:
        -----------
        database_url : str
            PostgreSQL connection string
        """
        # Create SQLAlchemy engine with connection pooling
        self.engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True  # Verify connections before use
        )
        
        # Create session factory for database operations
        self.Session = sessionmaker(bind=self.engine)
        
        # Metadata for table reflection and creation
        self.metadata = MetaData()
        
        # Storage for analysis results
        self.results: Dict[str, AnalysisResult] = {}
        
        # Network data storage
        self.network_edges: List[NetworkEdge] = []
        self.node_attributes: Dict[str, NodeAttributes] = {}
        
        # Dashboard aggregates
        self.dashboard_data: Dict[str, Any] = {}
        
        # Create output directories
        self._create_output_directories()
        
        logger.info("SixfoldAnalysisEngine initialized")
    
    def _create_output_directories(self):
        """Create output directories for external data storage."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        NETWORK_DIR.mkdir(parents=True, exist_ok=True)
        DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directories created at {OUTPUT_DIR}")
    
    # =========================================================================
    # DATABASE TABLE MANAGEMENT
    # =========================================================================
    
    def create_first_analysis_table(self) -> bool:
        """
        Create the `first_analysis` table if it doesn't exist.
        
        This table stores all analysis query results in a structured format,
        allowing for efficient retrieval and historical tracking.
        
        Returns:
        --------
        bool : True if table was created, False if it already existed
        """
        # Check if table already exists
        inspector = inspect(self.engine)
        if 'first_analysis' in inspector.get_table_names():
            logger.info("Table 'first_analysis' already exists")
            return False
        
        # Define the table schema
        # Input: Query results from all analysis sections
        # Algorithm: Store each query result as a JSON blob with metadata
        # Output: Structured table for API retrieval
        
        create_sql = text("""
            CREATE TABLE first_analysis (
                -- Primary identifier
                id SERIAL PRIMARY KEY,
                
                -- Query identification
                query_id VARCHAR(20) NOT NULL,           -- e.g., "1.1", "2.3"
                section INTEGER NOT NULL,                 -- Section number (0-8)
                category VARCHAR(100) NOT NULL,           -- Category name
                description TEXT NOT NULL,                -- Human-readable description
                query_type VARCHAR(50) NOT NULL,          -- overview, flow_matrix, top_n, etc.
                
                -- Result data
                result_data JSONB NOT NULL,               -- Query results as JSON
                row_count INTEGER NOT NULL,               -- Number of rows
                
                -- Metadata
                executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                analysis_version VARCHAR(20) DEFAULT '1.0',
                
                -- Unique constraint to prevent duplicates
                CONSTRAINT uq_query_id UNIQUE (query_id)
            );
            
            -- Indexes for efficient querying
            CREATE INDEX idx_first_analysis_section ON first_analysis(section);
            CREATE INDEX idx_first_analysis_category ON first_analysis(category);
            CREATE INDEX idx_first_analysis_query_type ON first_analysis(query_type);
            CREATE INDEX idx_first_analysis_executed_at ON first_analysis(executed_at);
            
            -- GIN index for JSONB queries
            CREATE INDEX idx_first_analysis_result_data ON first_analysis USING GIN (result_data);
            
            COMMENT ON TABLE first_analysis IS 
                'Stores all sixfold citation classification analysis results';
        """)
        
        with self.engine.begin() as conn:
            conn.execute(create_sql)
            logger.info("Table 'first_analysis' created successfully")
        
        return True
    
    def clear_first_analysis_table(self):
        """
        Clear all data from the first_analysis table.
        Used before repopulating with fresh analysis results.
        """
        with self.engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE first_analysis RESTART IDENTITY"))
            logger.info("Table 'first_analysis' cleared")
    
    def save_result_to_database(self, result: AnalysisResult):
        """
        Save a single analysis result to the first_analysis table.
        
        Parameters:
        -----------
        result : AnalysisResult
            The analysis result to save
        """
        # Use UPSERT to handle updates
        upsert_sql = text("""
            INSERT INTO first_analysis 
                (query_id, section, category, description, query_type, 
                 result_data, row_count, executed_at)
            VALUES 
                (:query_id, :section, :category, :description, :query_type,
                 :result_data, :row_count, :executed_at)
            ON CONFLICT (query_id) 
            DO UPDATE SET
                result_data = EXCLUDED.result_data,
                row_count = EXCLUDED.row_count,
                executed_at = EXCLUDED.executed_at
        """)
        
        with self.engine.begin() as conn:
            conn.execute(upsert_sql, {
                'query_id': result.query_id,
                'section': result.section,
                'category': result.category,
                'description': result.description,
                'query_type': result.query_type,
                'description': result.description,
                'query_type': result.query_type,
                'result_data': json.dumps(result.data, cls=DecimalEncoder),
                'row_count': result.row_count,
                'executed_at': result.executed_at
            })
    
    # =========================================================================
    # QUERY EXECUTION - Section 0: Overall Summary
    # =========================================================================
    
    def _execute_query(self, sql: str, params: Dict = None) -> List[Dict]:
        """
        Execute a SQL query and return results as list of dictionaries.
        
        Parameters:
        -----------
        sql : str
            SQL query string
        params : Dict, optional
            Query parameters
            
        Returns:
        --------
        List[Dict] : Query results
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
    
    def query_0_1_total_by_classification(self) -> AnalysisResult:
        """
        Query 0.1: Total citations by sixfold classification.
        
        Input: citation_sixfold_classification view
        Algorithm: GROUP BY sixfold_type and citation_direction
        Output: Count, decision count, and percentage for each type
        """
        sql = """
            SELECT 
                sixfold_type,
                citation_direction,
                COUNT(*) as citation_count,
                COUNT(DISTINCT document_id) as decision_count,
                ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) as pct_citations
            FROM citation_sixfold_classification
            GROUP BY sixfold_type, citation_direction
            ORDER BY citation_direction, sixfold_type
        """
        
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="0.1",
            section=0,
            category="Overall Summary",
            description="Total citations by sixfold classification",
            query_type="summary",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_0_2_summary_by_direction(self) -> AnalysisResult:
        """
        Query 0.2: Summary by citation direction.
        
        Input: citation_sixfold_classification view
        Algorithm: GROUP BY citation_direction only
        Output: Totals and percentages per direction
        """
        sql = """
            SELECT 
                citation_direction,
                COUNT(*) as total_citations,
                COUNT(DISTINCT document_id) as decisions_involved,
                ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) as pct
            FROM citation_sixfold_classification
            GROUP BY citation_direction
            ORDER BY total_citations DESC
        """
        
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="0.2",
            section=0,
            category="Overall Summary",
            description="Summary by citation direction",
            query_type="summary",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    # =========================================================================
    # QUERY EXECUTION - Section 1: Foreign Citation
    # =========================================================================
    
    def query_1_1_foreign_overview(self) -> AnalysisResult:
        """
        Query 1.1: Foreign Citation overview.
        
        Input: citation_sixfold_classification WHERE sixfold_type = 'Foreign Citation'
        Algorithm: Count totals for citations, decisions, and cases
        Output: Overview statistics
        """
        sql = """
            SELECT 
                COUNT(*) as total_citations,
                COUNT(DISTINCT document_id) as decisions_with_foreign,
                COUNT(DISTINCT case_id) as cases_with_foreign
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Foreign Citation'
        """
        
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="1.1",
            section=1,
            category="Foreign Citation",
            description="Foreign Citation overview",
            query_type="overview",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_1_2_regional_flow_matrix(self) -> AnalysisResult:
        """
        Query 1.2: Regional flow matrix (North-South).
        
        Input: Foreign citations with source/target regions
        Algorithm: Pivot table showing N→N, N→S, S→N, S→S flows
        Output: Matrix of citation flows
        """
        sql = """
            SELECT 
                source_region AS source,
                SUM(CASE WHEN case_law_region = 'Global North' THEN 1 ELSE 0 END) AS to_global_north,
                SUM(CASE WHEN case_law_region = 'Global South' THEN 1 ELSE 0 END) AS to_global_south,
                COUNT(*) AS total
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Foreign Citation'
              AND source_region IN ('Global North', 'Global South')
            GROUP BY source_region
            ORDER BY source_region
        """
        
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="1.2",
            section=1,
            category="Foreign Citation",
            description="Regional flow matrix (North-South)",
            query_type="flow_matrix",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_1_3_top_source_jurisdictions(self) -> AnalysisResult:
        """
        Query 1.3: Top 10 source jurisdictions (citing courts).
        
        Input: Foreign citations grouped by source jurisdiction
        Algorithm: COUNT and ORDER BY DESC, LIMIT 10
        Output: Top citing jurisdictions
        """
        sql = """
            SELECT 
                source_jurisdiction,
                source_region,
                COUNT(*) as citations_made
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Foreign Citation'
            GROUP BY source_jurisdiction, source_region
            ORDER BY citations_made DESC
            LIMIT 10
        """
        
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="1.3",
            section=1,
            category="Foreign Citation",
            description="Top 10 source jurisdictions (citing courts)",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_1_4_top_cited_jurisdictions(self) -> AnalysisResult:
        """
        Query 1.4: Top 10 cited jurisdictions.
        
        Input: Foreign citations grouped by case_law_origin
        Algorithm: COUNT and ORDER BY DESC, LIMIT 10
        Output: Most cited jurisdictions
        """
        sql = """
            SELECT 
                case_law_origin,
                case_law_region,
                COUNT(*) as times_cited
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Foreign Citation'
            GROUP BY case_law_origin, case_law_region
            ORDER BY times_cited DESC
            LIMIT 10
        """
        
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="1.4",
            section=1,
            category="Foreign Citation",
            description="Top 10 cited jurisdictions",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_1_5_top_cited_cases(self) -> AnalysisResult:
        """
        Query 1.5: Top 10 most cited cases (Foreign).
        
        Input: Foreign citations grouped by case_name
        Algorithm: COUNT and ORDER BY DESC, LIMIT 10
        Output: Most cited foreign cases
        """
        sql = """
            SELECT 
                case_name,
                case_law_origin,
                case_law_region,
                COUNT(*) as citation_count
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Foreign Citation'
            GROUP BY case_name, case_law_origin, case_law_region
            ORDER BY citation_count DESC
            LIMIT 10
        """
        
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="1.5",
            section=1,
            category="Foreign Citation",
            description="Top 10 most cited cases (Foreign)",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    # =========================================================================
    # QUERY EXECUTION - Section 2: International Citation
    # =========================================================================
    
    def query_2_1_international_overview(self) -> AnalysisResult:
        """Query 2.1: International Citation overview."""
        sql = """
            SELECT 
                COUNT(*) as total_citations,
                COUNT(DISTINCT document_id) as decisions_with_intl,
                COUNT(DISTINCT case_id) as cases_with_intl
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'International Citation'
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="2.1",
            section=2,
            category="International Citation",
            description="International Citation overview",
            query_type="overview",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_2_2_by_source_region(self) -> AnalysisResult:
        """Query 2.2: By source region (who cites international tribunals they belong to)."""
        sql = """
            SELECT 
                source_region,
                COUNT(*) as citations,
                COUNT(DISTINCT document_id) as decisions
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'International Citation'
            GROUP BY source_region
            ORDER BY citations DESC
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="2.2",
            section=2,
            category="International Citation",
            description="By source region (who cites international tribunals they belong to)",
            query_type="breakdown",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_2_3_top_source_jurisdictions(self) -> AnalysisResult:
        """Query 2.3: Top source jurisdictions citing their own tribunals."""
        sql = """
            SELECT 
                source_jurisdiction,
                source_region,
                COUNT(*) as citations_made
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'International Citation'
            GROUP BY source_jurisdiction, source_region
            ORDER BY citations_made DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="2.3",
            section=2,
            category="International Citation",
            description="Top source jurisdictions citing their own tribunals",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_2_4_most_cited_tribunals(self) -> AnalysisResult:
        """Query 2.4: Most cited international tribunals (by members)."""
        sql = """
            SELECT 
                case_law_origin,
                COUNT(*) as times_cited
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'International Citation'
            GROUP BY case_law_origin
            ORDER BY times_cited DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="2.4",
            section=2,
            category="International Citation",
            description="Most cited international tribunals (by members)",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_2_5_top_cited_cases(self) -> AnalysisResult:
        """Query 2.5: Top 10 most cited international cases (by member states)."""
        sql = """
            SELECT 
                case_name,
                case_law_origin,
                COUNT(*) as citation_count
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'International Citation'
            GROUP BY case_name, case_law_origin
            ORDER BY citation_count DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="2.5",
            section=2,
            category="International Citation",
            description="Top 10 most cited international cases (by member states)",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    # =========================================================================
    # QUERY EXECUTION - Section 3: Foreign International Citation
    # =========================================================================
    
    def query_3_1_foreign_intl_overview(self) -> AnalysisResult:
        """Query 3.1: Foreign International Citation overview."""
        sql = """
            SELECT 
                COUNT(*) as total_citations,
                COUNT(DISTINCT document_id) as decisions_with_foreign_intl,
                COUNT(DISTINCT case_id) as cases_with_foreign_intl
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Foreign International Citation'
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="3.1",
            section=3,
            category="Foreign International Citation",
            description="Foreign International Citation overview",
            query_type="overview",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_3_2_by_source_region(self) -> AnalysisResult:
        """Query 3.2: By source region (who cites tribunals they DON'T belong to)."""
        sql = """
            SELECT 
                source_region,
                COUNT(*) as citations,
                COUNT(DISTINCT document_id) as decisions
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Foreign International Citation'
            GROUP BY source_region
            ORDER BY citations DESC
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="3.2",
            section=3,
            category="Foreign International Citation",
            description="By source region (who cites tribunals they DON'T belong to)",
            query_type="breakdown",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_3_3_top_source_jurisdictions(self) -> AnalysisResult:
        """Query 3.3: Top source jurisdictions citing foreign tribunals."""
        sql = """
            SELECT 
                source_jurisdiction,
                source_region,
                COUNT(*) as citations_made
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Foreign International Citation'
            GROUP BY source_jurisdiction, source_region
            ORDER BY citations_made DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="3.3",
            section=3,
            category="Foreign International Citation",
            description="Top source jurisdictions citing foreign tribunals",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_3_4_most_cited_tribunals(self) -> AnalysisResult:
        """Query 3.4: Most cited foreign international tribunals."""
        sql = """
            SELECT 
                case_law_origin,
                COUNT(*) as times_cited
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Foreign International Citation'
            GROUP BY case_law_origin
            ORDER BY times_cited DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="3.4",
            section=3,
            category="Foreign International Citation",
            description="Most cited foreign international tribunals",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_3_5_top_cited_cases(self) -> AnalysisResult:
        """Query 3.5: Top 10 most cited foreign international cases."""
        sql = """
            SELECT 
                case_name,
                case_law_origin,
                COUNT(*) as citation_count
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Foreign International Citation'
            GROUP BY case_name, case_law_origin
            ORDER BY citation_count DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="3.5",
            section=3,
            category="Foreign International Citation",
            description="Top 10 most cited foreign international cases",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_3_6_cross_system_citations(self) -> AnalysisResult:
        """Query 3.6: Cross-system citations (e.g., Americas citing Europe)."""
        sql = """
            SELECT 
                source_jurisdiction,
                case_law_origin,
                COUNT(*) as citations
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Foreign International Citation'
            GROUP BY source_jurisdiction, case_law_origin
            ORDER BY citations DESC
            LIMIT 15
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="3.6",
            section=3,
            category="Foreign International Citation",
            description="Cross-system citations (e.g., Americas citing Europe)",
            query_type="cross_reference",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    # =========================================================================
    # QUERY EXECUTION - Section 4: Inter-System Citation
    # =========================================================================
    
    def query_4_1_intersystem_overview(self) -> AnalysisResult:
        """Query 4.1: Inter-System Citation overview."""
        sql = """
            SELECT 
                COUNT(*) as total_citations,
                COUNT(DISTINCT document_id) as decisions_with_intersystem,
                COUNT(DISTINCT case_id) as cases_with_intersystem
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Inter-System Citation'
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="4.1",
            section=4,
            category="Inter-System Citation",
            description="Inter-System Citation overview",
            query_type="overview",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_4_2_tribunal_to_tribunal_flows(self) -> AnalysisResult:
        """Query 4.2: Tribunal-to-tribunal citation flows."""
        sql = """
            SELECT 
                source_jurisdiction AS citing_tribunal,
                case_law_origin AS cited_tribunal,
                COUNT(*) as citation_count
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Inter-System Citation'
            GROUP BY source_jurisdiction, case_law_origin
            ORDER BY citation_count DESC
            LIMIT 15
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="4.2",
            section=4,
            category="Inter-System Citation",
            description="Tribunal-to-tribunal citation flows",
            query_type="flow_matrix",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_4_3_most_active_tribunals(self) -> AnalysisResult:
        """Query 4.3: Most active citing tribunals."""
        sql = """
            SELECT 
                source_jurisdiction,
                COUNT(*) as citations_made,
                COUNT(DISTINCT case_law_origin) as tribunals_cited
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Inter-System Citation'
            GROUP BY source_jurisdiction
            ORDER BY citations_made DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="4.3",
            section=4,
            category="Inter-System Citation",
            description="Most active citing tribunals",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_4_4_most_cited_tribunals(self) -> AnalysisResult:
        """Query 4.4: Most cited tribunals (by other tribunals)."""
        sql = """
            SELECT 
                case_law_origin,
                COUNT(*) as times_cited,
                COUNT(DISTINCT source_jurisdiction) as citing_tribunals
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Inter-System Citation'
            GROUP BY case_law_origin
            ORDER BY times_cited DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="4.4",
            section=4,
            category="Inter-System Citation",
            description="Most cited tribunals (by other tribunals)",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_4_5_top_cited_cases(self) -> AnalysisResult:
        """Query 4.5: Top 10 most cited inter-system cases."""
        sql = """
            SELECT 
                case_name,
                case_law_origin,
                COUNT(*) as citation_count
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Inter-System Citation'
            GROUP BY case_name, case_law_origin
            ORDER BY citation_count DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="4.5",
            section=4,
            category="Inter-System Citation",
            description="Top 10 most cited inter-system cases",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    # =========================================================================
    # QUERY EXECUTION - Section 5: Member-State Citation
    # =========================================================================
    
    def query_5_1_member_state_overview(self) -> AnalysisResult:
        """Query 5.1: Member-State Citation overview."""
        sql = """
            SELECT 
                COUNT(*) as total_citations,
                COUNT(DISTINCT document_id) as decisions_with_member_state,
                COUNT(DISTINCT case_id) as cases_with_member_state
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Member-State Citation'
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="5.1",
            section=5,
            category="Member-State Citation",
            description="Member-State Citation overview",
            query_type="overview",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_5_2_by_cited_region(self) -> AnalysisResult:
        """Query 5.2: By cited region (which regions do tribunals cite from their members)."""
        sql = """
            SELECT 
                case_law_region AS cited_region,
                COUNT(*) as citations,
                COUNT(DISTINCT document_id) as decisions
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Member-State Citation'
            GROUP BY case_law_region
            ORDER BY citations DESC
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="5.2",
            section=5,
            category="Member-State Citation",
            description="By cited region (which regions do tribunals cite from their members)",
            query_type="breakdown",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_5_3_top_source_tribunals(self) -> AnalysisResult:
        """Query 5.3: Top source tribunals citing their member states."""
        sql = """
            SELECT 
                source_jurisdiction,
                COUNT(*) as citations_made,
                COUNT(DISTINCT case_law_origin) as member_states_cited
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Member-State Citation'
            GROUP BY source_jurisdiction
            ORDER BY citations_made DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="5.3",
            section=5,
            category="Member-State Citation",
            description="Top source tribunals citing their member states",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_5_4_most_cited_jurisdictions(self) -> AnalysisResult:
        """Query 5.4: Most cited member state jurisdictions."""
        sql = """
            SELECT 
                case_law_origin,
                case_law_region,
                COUNT(*) as times_cited
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Member-State Citation'
            GROUP BY case_law_origin, case_law_region
            ORDER BY times_cited DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="5.4",
            section=5,
            category="Member-State Citation",
            description="Most cited member state jurisdictions",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_5_5_top_cited_cases(self) -> AnalysisResult:
        """Query 5.5: Top 10 most cited member state cases."""
        sql = """
            SELECT 
                case_name,
                case_law_origin,
                case_law_region,
                COUNT(*) as citation_count
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Member-State Citation'
            GROUP BY case_name, case_law_origin, case_law_region
            ORDER BY citation_count DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="5.5",
            section=5,
            category="Member-State Citation",
            description="Top 10 most cited member state cases",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    # =========================================================================
    # QUERY EXECUTION - Section 6: Non-Member Citation
    # =========================================================================
    
    def query_6_1_non_member_overview(self) -> AnalysisResult:
        """Query 6.1: Non-Member Citation overview."""
        sql = """
            SELECT 
                COUNT(*) as total_citations,
                COUNT(DISTINCT document_id) as decisions_with_non_member,
                COUNT(DISTINCT case_id) as cases_with_non_member
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Non-Member Citation'
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="6.1",
            section=6,
            category="Non-Member Citation",
            description="Non-Member Citation overview",
            query_type="overview",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_6_2_by_cited_region(self) -> AnalysisResult:
        """Query 6.2: By cited region (which regions do tribunals cite outside their system)."""
        sql = """
            SELECT 
                case_law_region AS cited_region,
                COUNT(*) as citations,
                COUNT(DISTINCT document_id) as decisions
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Non-Member Citation'
            GROUP BY case_law_region
            ORDER BY citations DESC
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="6.2",
            section=6,
            category="Non-Member Citation",
            description="By cited region (which regions do tribunals cite outside their system)",
            query_type="breakdown",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_6_3_top_source_tribunals(self) -> AnalysisResult:
        """Query 6.3: Top source tribunals citing non-member states."""
        sql = """
            SELECT 
                source_jurisdiction,
                COUNT(*) as citations_made,
                COUNT(DISTINCT case_law_origin) as non_members_cited
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Non-Member Citation'
            GROUP BY source_jurisdiction
            ORDER BY citations_made DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="6.3",
            section=6,
            category="Non-Member Citation",
            description="Top source tribunals citing non-member states",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_6_4_most_cited_jurisdictions(self) -> AnalysisResult:
        """Query 6.4: Most cited non-member state jurisdictions."""
        sql = """
            SELECT 
                case_law_origin,
                case_law_region,
                COUNT(*) as times_cited
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Non-Member Citation'
            GROUP BY case_law_origin, case_law_region
            ORDER BY times_cited DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="6.4",
            section=6,
            category="Non-Member Citation",
            description="Most cited non-member state jurisdictions",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_6_5_top_cited_cases(self) -> AnalysisResult:
        """Query 6.5: Top 10 most cited non-member state cases."""
        sql = """
            SELECT 
                case_name,
                case_law_origin,
                case_law_region,
                COUNT(*) as citation_count
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Non-Member Citation'
            GROUP BY case_name, case_law_origin, case_law_region
            ORDER BY citation_count DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="6.5",
            section=6,
            category="Non-Member Citation",
            description="Top 10 most cited non-member state cases",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_6_6_cross_regional_citations(self) -> AnalysisResult:
        """Query 6.6: Cross-regional citations (tribunals citing outside their region)."""
        sql = """
            SELECT 
                source_jurisdiction AS citing_tribunal,
                case_law_origin AS cited_jurisdiction,
                case_law_region,
                COUNT(*) as citations
            FROM citation_sixfold_classification
            WHERE sixfold_type = 'Non-Member Citation'
            GROUP BY source_jurisdiction, case_law_origin, case_law_region
            ORDER BY citations DESC
            LIMIT 15
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="6.6",
            section=6,
            category="Non-Member Citation",
            description="Cross-regional citations (tribunals citing outside their region)",
            query_type="cross_reference",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    # =========================================================================
    # QUERY EXECUTION - Section 7: Comparative Analysis
    # =========================================================================
    
    def query_7_1_decisions_by_types(self) -> AnalysisResult:
        """Query 7.1: Decisions by number of citation types present."""
        sql = """
            WITH decision_types AS (
                SELECT 
                    document_id,
                    COUNT(DISTINCT sixfold_type) as num_types,
                    STRING_AGG(DISTINCT sixfold_type, ', ' ORDER BY sixfold_type) as types_present
                FROM citation_sixfold_classification
                GROUP BY document_id
            )
            SELECT 
                num_types AS citation_types_present,
                COUNT(*) as number_of_decisions,
                ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 1) as percentage
            FROM decision_types
            GROUP BY num_types
            ORDER BY num_types
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="7.1",
            section=7,
            category="Comparative Analysis",
            description="Decisions by number of citation types present",
            query_type="distribution",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_7_2_north_south_asymmetry(self) -> AnalysisResult:
        """Query 7.2: North-South asymmetry across all relevant categories."""
        sql = """
            SELECT 
                sixfold_type,
                SUM(CASE WHEN source_region = 'Global North' AND case_law_region = 'Global North' THEN 1 ELSE 0 END) AS n_to_n,
                SUM(CASE WHEN source_region = 'Global North' AND case_law_region = 'Global South' THEN 1 ELSE 0 END) AS n_to_s,
                SUM(CASE WHEN source_region = 'Global South' AND case_law_region = 'Global North' THEN 1 ELSE 0 END) AS s_to_n,
                SUM(CASE WHEN source_region = 'Global South' AND case_law_region = 'Global South' THEN 1 ELSE 0 END) AS s_to_s,
                COUNT(*) AS total
            FROM citation_sixfold_classification
            WHERE sixfold_type IN ('Foreign Citation', 'Member-State Citation', 'Non-Member Citation')
            GROUP BY sixfold_type
            ORDER BY sixfold_type
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="7.2",
            section=7,
            category="Comparative Analysis",
            description="North-South asymmetry across all relevant categories",
            query_type="asymmetry",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_7_3_global_south_engagement(self) -> AnalysisResult:
        """Query 7.3: Global South engagement summary."""
        sql = """
            SELECT 
                sixfold_type,
                COUNT(*) FILTER (WHERE source_region = 'Global South') AS citations_from_south,
                COUNT(*) FILTER (WHERE case_law_region = 'Global South') AS citations_to_south,
                COUNT(*) AS total_citations
            FROM citation_sixfold_classification
            GROUP BY sixfold_type
            ORDER BY citations_from_south DESC
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="7.3",
            section=7,
            category="Comparative Analysis",
            description="Global South engagement summary",
            query_type="engagement",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    def query_7_4_top_cited_overall(self) -> AnalysisResult:
        """Query 7.4: Top 10 most cited cases overall (all categories)."""
        sql = """
            SELECT 
                case_name,
                case_law_origin,
                case_law_region,
                sixfold_type,
                COUNT(*) as citation_count
            FROM citation_sixfold_classification
            GROUP BY case_name, case_law_origin, case_law_region, sixfold_type
            ORDER BY citation_count DESC
            LIMIT 10
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="7.4",
            section=7,
            category="Comparative Analysis",
            description="Top 10 most cited cases overall (all categories)",
            query_type="top_n",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    # =========================================================================
    # QUERY EXECUTION - Section 8: Export-Ready Summary
    # =========================================================================
    
    def query_8_1_final_summary(self) -> AnalysisResult:
        """Query 8.1: Final summary table (for thesis)."""
        sql = """
            SELECT 
                sixfold_type AS citation_category,
                citation_direction AS direction,
                COUNT(*) AS total_citations,
                COUNT(DISTINCT document_id) AS decisions,
                COUNT(DISTINCT case_id) AS cases,
                ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) AS pct_of_total
            FROM citation_sixfold_classification
            GROUP BY sixfold_type, citation_direction
            ORDER BY 
                CASE citation_direction 
                    WHEN 'National → National' THEN 1
                    WHEN 'National → International' THEN 2
                    WHEN 'International → International' THEN 3
                    WHEN 'International → National' THEN 4
                    ELSE 5
                END,
                sixfold_type
        """
        data = self._execute_query(sql)
        
        return AnalysisResult(
            query_id="8.1",
            section=8,
            category="Export-Ready Summary",
            description="Final summary table (for thesis)",
            query_type="export",
            data=data,
            row_count=len(data),
            executed_at=datetime.now()
        )
    
    # =========================================================================
    # NETWORK DATA GENERATION
    # =========================================================================
    
    def generate_jurisdiction_network(self) -> List[NetworkEdge]:
        """
        Generate jurisdiction-level network edges for visualization.
        
        Input: citation_sixfold_classification view
        Algorithm: Aggregate citations by source_jurisdiction → case_law_origin
        Output: List of NetworkEdge objects with weights
        """
        sql = """
            SELECT 
                source_jurisdiction,
                case_law_origin,
                source_region,
                case_law_region,
                sixfold_type,
                COUNT(*) as weight
            FROM citation_sixfold_classification
            WHERE source_jurisdiction IS NOT NULL 
              AND case_law_origin IS NOT NULL
            GROUP BY source_jurisdiction, case_law_origin, 
                     source_region, case_law_region, sixfold_type
            ORDER BY weight DESC
        """
        
        data = self._execute_query(sql)
        
        edges = []
        for row in data:
            # Get coordinates for source and target
            source_coords = JURISDICTION_COORDINATES.get(row['source_jurisdiction'], {})
            target_coords = JURISDICTION_COORDINATES.get(row['case_law_origin'], {})
            
            edge = NetworkEdge(
                source=row['source_jurisdiction'],
                target=row['case_law_origin'],
                source_type='jurisdiction',
                target_type='jurisdiction',
                source_region=row['source_region'] or 'Unknown',
                target_region=row['case_law_region'] or 'Unknown',
                weight=row['weight'],
                sixfold_type=row['sixfold_type']
            )
            # Add coordinates dynamically since they are not in __init__
            # Note: NetworkEdge is a dataclass, so we can't easily add fields without changing definition
            # But we added them to NodeAttributes, which is where they are needed for the map

            edges.append(edge)
        
        self.network_edges = edges
        logger.info(f"Generated {len(edges)} jurisdiction network edges")
        return edges
    
    def generate_node_attributes(self) -> Dict[str, NodeAttributes]:
        """
        Generate node attributes for network visualization.
        
        Input: Network edges
        Algorithm: Calculate in-degree, out-degree, total degree for each node
        Output: Dictionary of NodeAttributes keyed by node_id
        """
        # Calculate degrees from edges
        in_degree: Dict[str, int] = {}
        out_degree: Dict[str, int] = {}
        node_regions: Dict[str, str] = {}
        
        for edge in self.network_edges:
            # Out-degree for source
            out_degree[edge.source] = out_degree.get(edge.source, 0) + edge.weight
            node_regions[edge.source] = edge.source_region
            
            # In-degree for target
            in_degree[edge.target] = in_degree.get(edge.target, 0) + edge.weight
            node_regions[edge.target] = edge.target_region
        
        # Create node attributes
        all_nodes = set(in_degree.keys()) | set(out_degree.keys())
        nodes = {}
        
        for node_id in all_nodes:
            in_d = in_degree.get(node_id, 0)
            out_d = out_degree.get(node_id, 0)
            
            # Get coordinates
            coords = JURISDICTION_COORDINATES.get(node_id, {})
            
            nodes[node_id] = NodeAttributes(
                node_id=node_id,
                node_type='jurisdiction',
                label=node_id,
                region=node_regions.get(node_id, 'Unknown'),
                in_degree=in_d,
                out_degree=out_d,
                total_degree=in_d + out_d,
                lat=coords.get('lat'),
                lon=coords.get('lon')
            )
        
        self.node_attributes = nodes
        logger.info(f"Generated attributes for {len(nodes)} nodes")
        return nodes
    
    def export_network_data(self):
        """
        Export network data to JSON and CSV files.
        
        Output files:
        - network_data/edges.json: All edges with attributes
        - network_data/edges.csv: CSV format for D3.js/Gephi
        - network_data/nodes.json: Node attributes
        - network_data/nodes.csv: CSV format for visualization tools
        """
        # Ensure network data is generated
        if not self.network_edges:
            self.generate_jurisdiction_network()
        if not self.node_attributes:
            self.generate_node_attributes()
        
        # Export edges to JSON
        edges_json = [e.to_dict() for e in self.network_edges]
        with open(NETWORK_DIR / 'edges.json', 'w', encoding='utf-8') as f:
            json.dump(edges_json, f, indent=2, ensure_ascii=False, cls=DecimalEncoder)
        
        # Export edges to CSV
        edges_df = pd.DataFrame(edges_json)
        edges_df.to_csv(NETWORK_DIR / 'edges.csv', index=False)
        
        # Export nodes to JSON
        nodes_json = {k: v.to_dict() for k, v in self.node_attributes.items()}
        with open(NETWORK_DIR / 'nodes.json', 'w', encoding='utf-8') as f:
            json.dump(nodes_json, f, indent=2, ensure_ascii=False, cls=DecimalEncoder)
        
        # Export nodes to CSV
        nodes_df = pd.DataFrame([v.to_dict() for v in self.node_attributes.values()])
        nodes_df.to_csv(NETWORK_DIR / 'nodes.csv', index=False)
        
        # Export D3.js-compatible format
        d3_data = {
            'nodes': [
                {
                    'id': node.node_id,
                    'label': node.label,
                    'region': node.region,
                    'in_degree': node.in_degree,
                    'out_degree': node.out_degree,
                    'total_degree': node.total_degree,
                    'lat': node.lat,
                    'lon': node.lon
                }
                for node in self.node_attributes.values()
            ],
            'links': [
                {
                    'source': edge.source,
                    'target': edge.target,
                    'value': edge.weight,
                    'type': edge.sixfold_type
                }
                for edge in self.network_edges
            ]
        }
        with open(NETWORK_DIR / 'd3_network.json', 'w', encoding='utf-8') as f:
            json.dump(d3_data, f, indent=2, ensure_ascii=False, cls=DecimalEncoder)
        
        logger.info(f"Network data exported to {NETWORK_DIR}")
    
    # =========================================================================
    # DASHBOARD AGGREGATES
    # =========================================================================
    
    def generate_dashboard_aggregates(self):
        """
        Generate aggregate data for dashboard visualizations.
        
        Creates pre-computed aggregates optimized for frontend display.
        
        Output files in dashboard_data/:
        - summary_stats.json: High-level statistics
        - category_breakdown.json: By sixfold category
        - regional_flows.json: North-South flow data
        - top_cases.json: Most cited cases by category
        - time_series.json: Citations over time (if date available)
        """
        dashboard = {}
        
        # 1. Summary statistics
        summary_result = self.query_8_1_final_summary()
        dashboard['summary_stats'] = {
            'total_citations': sum(r['total_citations'] for r in summary_result.data),
            'total_decisions': sum(r['decisions'] for r in summary_result.data),
            'total_cases': sum(r['cases'] for r in summary_result.data),
            'by_category': summary_result.data,
            'generated_at': datetime.now().isoformat()
        }
        
        # 2. Category breakdown with details
        category_data = {}
        
        # Section 1: Foreign
        foreign_overview = self.query_1_1_foreign_overview()
        foreign_flow = self.query_1_2_regional_flow_matrix()
        category_data['Foreign Citation'] = {
            'overview': foreign_overview.data[0] if foreign_overview.data else {},
            'flow_matrix': foreign_flow.data,
            'top_sources': self.query_1_3_top_source_jurisdictions().data,
            'top_cited': self.query_1_4_top_cited_jurisdictions().data,
            'top_cases': self.query_1_5_top_cited_cases().data
        }
        
        # Section 2: International
        category_data['International Citation'] = {
            'overview': self.query_2_1_international_overview().data[0] if self.query_2_1_international_overview().data else {},
            'by_region': self.query_2_2_by_source_region().data,
            'top_sources': self.query_2_3_top_source_jurisdictions().data,
            'top_tribunals': self.query_2_4_most_cited_tribunals().data,
            'top_cases': self.query_2_5_top_cited_cases().data
        }
        
        # Section 3: Foreign International
        category_data['Foreign International Citation'] = {
            'overview': self.query_3_1_foreign_intl_overview().data[0] if self.query_3_1_foreign_intl_overview().data else {},
            'by_region': self.query_3_2_by_source_region().data,
            'top_sources': self.query_3_3_top_source_jurisdictions().data,
            'top_tribunals': self.query_3_4_most_cited_tribunals().data,
            'top_cases': self.query_3_5_top_cited_cases().data,
            'cross_system': self.query_3_6_cross_system_citations().data
        }
        
        # Section 4: Inter-System
        category_data['Inter-System Citation'] = {
            'overview': self.query_4_1_intersystem_overview().data[0] if self.query_4_1_intersystem_overview().data else {},
            'flows': self.query_4_2_tribunal_to_tribunal_flows().data,
            'active_tribunals': self.query_4_3_most_active_tribunals().data,
            'cited_tribunals': self.query_4_4_most_cited_tribunals().data,
            'top_cases': self.query_4_5_top_cited_cases().data
        }
        
        # Section 5: Member-State
        category_data['Member-State Citation'] = {
            'overview': self.query_5_1_member_state_overview().data[0] if self.query_5_1_member_state_overview().data else {},
            'by_region': self.query_5_2_by_cited_region().data,
            'top_tribunals': self.query_5_3_top_source_tribunals().data,
            'top_jurisdictions': self.query_5_4_most_cited_jurisdictions().data,
            'top_cases': self.query_5_5_top_cited_cases().data
        }
        
        # Section 6: Non-Member
        category_data['Non-Member Citation'] = {
            'overview': self.query_6_1_non_member_overview().data[0] if self.query_6_1_non_member_overview().data else {},
            'by_region': self.query_6_2_by_cited_region().data,
            'top_tribunals': self.query_6_3_top_source_tribunals().data,
            'top_jurisdictions': self.query_6_4_most_cited_jurisdictions().data,
            'top_cases': self.query_6_5_top_cited_cases().data,
            'cross_regional': self.query_6_6_cross_regional_citations().data
        }
        
        dashboard['category_breakdown'] = category_data
        
        # 3. Regional flows (for Sankey/chord diagrams)
        regional_flows = self.query_7_2_north_south_asymmetry()
        dashboard['regional_flows'] = {
            'asymmetry_data': regional_flows.data,
            'global_south_engagement': self.query_7_3_global_south_engagement().data
        }
        
        # 4. Comparative analysis
        dashboard['comparative'] = {
            'types_distribution': self.query_7_1_decisions_by_types().data,
            'top_cases_overall': self.query_7_4_top_cited_overall().data
        }
        
        self.dashboard_data = dashboard
        
        # Save to files
        with open(DASHBOARD_DIR / 'summary_stats.json', 'w', encoding='utf-8') as f:
            json.dump(dashboard['summary_stats'], f, indent=2, ensure_ascii=False, cls=DecimalEncoder)
        
        with open(DASHBOARD_DIR / 'category_breakdown.json', 'w', encoding='utf-8') as f:
            json.dump(dashboard['category_breakdown'], f, indent=2, ensure_ascii=False, cls=DecimalEncoder)
        
        with open(DASHBOARD_DIR / 'regional_flows.json', 'w', encoding='utf-8') as f:
            json.dump(dashboard['regional_flows'], f, indent=2, ensure_ascii=False, cls=DecimalEncoder)
        
        with open(DASHBOARD_DIR / 'comparative.json', 'w', encoding='utf-8') as f:
            json.dump(dashboard['comparative'], f, indent=2, ensure_ascii=False, cls=DecimalEncoder)
        
        # Complete dashboard bundle for frontend
        with open(DASHBOARD_DIR / 'dashboard_complete.json', 'w', encoding='utf-8') as f:
            json.dump(dashboard, f, indent=2, ensure_ascii=False, cls=DecimalEncoder)
        
        logger.info(f"Dashboard aggregates exported to {DASHBOARD_DIR}")
    
    # =========================================================================
    # MAIN EXECUTION METHODS
    # =========================================================================
    
    def run_all_queries(self) -> Dict[str, AnalysisResult]:
        """
        Execute all analysis queries and store results.
        
        Returns:
        --------
        Dict[str, AnalysisResult] : All results keyed by query_id
        """
        logger.info("Starting full query execution...")
        
        # Section 0: Overall Summary
        self.results['0.1'] = self.query_0_1_total_by_classification()
        self.results['0.2'] = self.query_0_2_summary_by_direction()
        
        # Section 1: Foreign Citation
        self.results['1.1'] = self.query_1_1_foreign_overview()
        self.results['1.2'] = self.query_1_2_regional_flow_matrix()
        self.results['1.3'] = self.query_1_3_top_source_jurisdictions()
        self.results['1.4'] = self.query_1_4_top_cited_jurisdictions()
        self.results['1.5'] = self.query_1_5_top_cited_cases()
        
        # Section 2: International Citation
        self.results['2.1'] = self.query_2_1_international_overview()
        self.results['2.2'] = self.query_2_2_by_source_region()
        self.results['2.3'] = self.query_2_3_top_source_jurisdictions()
        self.results['2.4'] = self.query_2_4_most_cited_tribunals()
        self.results['2.5'] = self.query_2_5_top_cited_cases()
        
        # Section 3: Foreign International Citation
        self.results['3.1'] = self.query_3_1_foreign_intl_overview()
        self.results['3.2'] = self.query_3_2_by_source_region()
        self.results['3.3'] = self.query_3_3_top_source_jurisdictions()
        self.results['3.4'] = self.query_3_4_most_cited_tribunals()
        self.results['3.5'] = self.query_3_5_top_cited_cases()
        self.results['3.6'] = self.query_3_6_cross_system_citations()
        
        # Section 4: Inter-System Citation
        self.results['4.1'] = self.query_4_1_intersystem_overview()
        self.results['4.2'] = self.query_4_2_tribunal_to_tribunal_flows()
        self.results['4.3'] = self.query_4_3_most_active_tribunals()
        self.results['4.4'] = self.query_4_4_most_cited_tribunals()
        self.results['4.5'] = self.query_4_5_top_cited_cases()
        
        # Section 5: Member-State Citation
        self.results['5.1'] = self.query_5_1_member_state_overview()
        self.results['5.2'] = self.query_5_2_by_cited_region()
        self.results['5.3'] = self.query_5_3_top_source_tribunals()
        self.results['5.4'] = self.query_5_4_most_cited_jurisdictions()
        self.results['5.5'] = self.query_5_5_top_cited_cases()
        
        # Section 6: Non-Member Citation
        self.results['6.1'] = self.query_6_1_non_member_overview()
        self.results['6.2'] = self.query_6_2_by_cited_region()
        self.results['6.3'] = self.query_6_3_top_source_tribunals()
        self.results['6.4'] = self.query_6_4_most_cited_jurisdictions()
        self.results['6.5'] = self.query_6_5_top_cited_cases()
        self.results['6.6'] = self.query_6_6_cross_regional_citations()
        
        # Section 7: Comparative Analysis
        self.results['7.1'] = self.query_7_1_decisions_by_types()
        self.results['7.2'] = self.query_7_2_north_south_asymmetry()
        self.results['7.3'] = self.query_7_3_global_south_engagement()
        self.results['7.4'] = self.query_7_4_top_cited_overall()
        
        # Section 8: Export Summary
        self.results['8.1'] = self.query_8_1_final_summary()
        
        logger.info(f"Executed {len(self.results)} queries successfully")
        return self.results
    
    def save_all_results_to_database(self):
        """
        Save all query results to the first_analysis table.
        Clears existing data and repopulates.
        """
        logger.info("Saving results to database...")
        
        # Ensure table exists
        self.create_first_analysis_table()
        
        # Clear existing data
        self.clear_first_analysis_table()
        
        # Save each result
        for query_id, result in self.results.items():
            self.save_result_to_database(result)
            logger.debug(f"Saved query {query_id}")
        
        logger.info(f"Saved {len(self.results)} results to first_analysis table")
    
    def run_full_analysis(self):
        """
        Run the complete analysis pipeline:
        1. Execute all queries
        2. Save to database
        3. Generate network data
        4. Generate dashboard aggregates
        """
        logger.info("=" * 60)
        logger.info("SIXFOLD CITATION CLASSIFICATION - FULL ANALYSIS")
        logger.info("=" * 60)
        
        # Step 1: Execute queries
        logger.info("\n[Step 1/4] Executing analysis queries...")
        self.run_all_queries()
        
        # Step 2: Save to database
        logger.info("\n[Step 2/4] Saving results to database...")
        self.save_all_results_to_database()
        
        # Step 3: Generate network data
        logger.info("\n[Step 3/4] Generating network data...")
        self.generate_jurisdiction_network()
        self.generate_node_attributes()
        self.export_network_data()
        
        # Step 4: Generate dashboard aggregates
        logger.info("\n[Step 4/4] Generating dashboard aggregates...")
        self.generate_dashboard_aggregates()
        
        logger.info("\n" + "=" * 60)
        logger.info("ANALYSIS COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Results saved to database: first_analysis table")
        logger.info(f"Network data exported to: {NETWORK_DIR}")
        logger.info(f"Dashboard data exported to: {DASHBOARD_DIR}")
    
    # =========================================================================
    # API METHODS - For Frontend Integration
    # =========================================================================
    
    def get_result(self, query_id: str) -> Optional[Dict]:
        """
        API method: Get a specific query result.
        
        Parameters:
        -----------
        query_id : str
            Query identifier (e.g., "1.1", "2.3")
            
        Returns:
        --------
        Dict or None : Query result data
        """
        if query_id in self.results:
            return self.results[query_id].to_dict()
        
        # Try to fetch from database
        sql = text("SELECT * FROM first_analysis WHERE query_id = :qid")
        with self.engine.connect() as conn:
            result = conn.execute(sql, {'qid': query_id}).fetchone()
            if result:
                return {
                    'query_id': result.query_id,
                    'section': result.section,
                    'category': result.category,
                    'description': result.description,
                    'query_type': result.query_type,
                    'data': result.result_data,
                    'row_count': result.row_count,
                    'executed_at': result.executed_at.isoformat()
                }
        return None
    
    def get_section_results(self, section: int) -> List[Dict]:
        """
        API method: Get all results for a section.
        
        Parameters:
        -----------
        section : int
            Section number (0-8)
            
        Returns:
        --------
        List[Dict] : All query results for the section
        """
        sql = text("SELECT * FROM first_analysis WHERE section = :sec ORDER BY query_id")
        with self.engine.connect() as conn:
            results = conn.execute(sql, {'sec': section}).fetchall()
            return [
                {
                    'query_id': r.query_id,
                    'description': r.description,
                    'query_type': r.query_type,
                    'data': r.result_data,
                    'row_count': r.row_count
                }
                for r in results
            ]
    
    def get_dashboard_data(self) -> Dict:
        """
        API method: Get complete dashboard data.
        
        Returns:
        --------
        Dict : Dashboard aggregates
        """
        if self.dashboard_data:
            return self.dashboard_data
        
        # Load from file
        dashboard_file = DASHBOARD_DIR / 'dashboard_complete.json'
        if dashboard_file.exists():
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return {}
    
    def get_network_data(self) -> Dict:
        """
        API method: Get network data for visualization.
        
        Returns:
        --------
        Dict : D3.js-compatible network data
        """
        network_file = NETWORK_DIR / 'd3_network.json'
        if network_file.exists():
            with open(network_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'nodes': [], 'links': []}


# =============================================================================
# COMMAND-LINE INTERFACE
# =============================================================================

def main():
    """
    Main entry point for command-line execution.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Sixfold Citation Classification Analysis Engine'
    )
    parser.add_argument(
        '--db-url',
        default=DATABASE_URL,
        help='PostgreSQL connection URL'
    )
    parser.add_argument(
        '--output-dir',
        default=str(OUTPUT_DIR),
        help='Output directory for external data'
    )
    parser.add_argument(
        '--queries-only',
        action='store_true',
        help='Run queries only, skip network and dashboard generation'
    )
    parser.add_argument(
        '--network-only',
        action='store_true',
        help='Generate network data only (requires prior query execution)'
    )
    parser.add_argument(
        '--dashboard-only',
        action='store_true',
        help='Generate dashboard data only (requires prior query execution)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Update output directory if specified
    # Update output directory if specified
    output_path = Path(args.output_dir)
    NETWORK_DIR = output_path / 'network_data'
    DASHBOARD_DIR = output_path / 'dashboard_data'
    
    # Initialize engine
    engine = SixfoldAnalysisEngine(database_url=args.db_url)
    
    # Execute based on flags
    if args.queries_only:
        engine.run_all_queries()
        engine.save_all_results_to_database()
    elif args.network_only:
        engine.generate_jurisdiction_network()
        engine.generate_node_attributes()
        engine.export_network_data()
    elif args.dashboard_only:
        engine.run_all_queries()  # Needed for dashboard
        engine.generate_dashboard_aggregates()
    else:
        engine.run_full_analysis()
    
    print("\n✓ Analysis complete!")
    print(f"  Output directory: {output_path}")


if __name__ == '__main__':
    main()
