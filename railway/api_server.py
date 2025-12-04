#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
SIXFOLD CITATION CLASSIFICATION - REST API SERVER
============================================================================

Climate Litigation PhD Research Project
Author: Gustavo (with Claude assistance)
Date: November 28, 2025

Purpose:
--------
This module provides a REST API for the sixfold analysis engine, enabling:
- Frontend (HTML/JS) to query analysis results
- Data visualization endpoints for charts and networks
- Export functionality for custom data exports
- Real-time analysis refresh capabilities

Tech Stack:
-----------
- Flask (lightweight web framework)
- Flask-CORS (cross-origin support for frontend)
- SQLAlchemy (via sixfold_analysis_engine)

Usage:
------
    # Development server:
    python api_server.py
    
    # Production (with gunicorn):
    gunicorn -w 4 -b 0.0.0.0:5000 api_server:app

Endpoints:
----------
    GET  /api/health              - Health check
    GET  /api/analysis/run        - Run full analysis
    GET  /api/results/<query_id>  - Get specific query result
    GET  /api/sections/<section>  - Get all results for a section
    GET  /api/dashboard           - Get dashboard aggregates
    GET  /api/network             - Get network visualization data
    GET  /api/export/<format>     - Export data in various formats

============================================================================
"""

import sys
print("DEBUG: Starting api_server.py...", file=sys.stdout, flush=True)

import os
import json
import io
import csv
print("DEBUG: Imports complete...", file=sys.stdout, flush=True)
from datetime import datetime
from functools import wraps
from typing import Dict, Any, Optional

# Flask imports
from flask import Flask, jsonify, request, send_file, Response, render_template
from flask_cors import CORS

# Import our analysis engine
print("DEBUG: Importing SixfoldAnalysisEngine...", file=sys.stdout, flush=True)
from sixfold_analysis_engine import (
    SixfoldAnalysisEngine,
    OUTPUT_DIR,
    NETWORK_DIR,
    DASHBOARD_DIR,
    DATABASE_URL
)
print("DEBUG: SixfoldAnalysisEngine imported.", file=sys.stdout, flush=True)

# =============================================================================
# PRODUCTION ENVIRONMENT CONFIGURATION
# =============================================================================

import logging

# Configure logging for production
IS_RAILWAY = os.getenv('RAILWAY_ENVIRONMENT') or os.getenv('RAILWAY_ENVIRONMENT_NAME')

if IS_RAILWAY:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

# Handle Railway's DATABASE_URL format
# Railway provides postgres:// but SQLAlchemy 2.0+ requires postgresql://
_production_db_url = os.getenv('DATABASE_URL')
if _production_db_url:
    if _production_db_url.startswith('postgres://'):
        _production_db_url = _production_db_url.replace('postgres://', 'postgresql://', 1)
    # Override the imported DATABASE_URL with production version
    DATABASE_URL = _production_db_url

# Determine environment for logging and CORS
IS_PRODUCTION = IS_RAILWAY is not None

# =============================================================================
# FLASK APPLICATION SETUP
# =============================================================================

app = Flask(__name__)

# =============================================================================
# CORS CONFIGURATION
# =============================================================================
# In production, restrict to Railway frontend domain
# In development, allow all origins for flexibility

if IS_PRODUCTION:
    # Get frontend URL from environment variable, or allow all Railway domains
    frontend_url = os.getenv('FRONTEND_URL', '*')
    CORS(app, resources={r"/api/*": {"origins": frontend_url}})
    app.logger.info(f"CORS configured for production: {frontend_url}")
else:
    # Development: allow all origins (localhost, file://, etc.)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuration
app.config['JSON_SORT_KEYS'] = False  # Preserve order in JSON responses
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Global engine instance (lazy initialization)
_engine: Optional[SixfoldAnalysisEngine] = None


def get_engine() -> SixfoldAnalysisEngine:
    """
    Get or create the analysis engine singleton.
    Uses production DATABASE_URL if available, otherwise falls back to local.
    
    Returns:
    --------
    SixfoldAnalysisEngine : Initialized engine instance
    """
    global _engine
    if _engine is None:
        # DATABASE_URL is already processed above (postgres:// → postgresql://)
        _engine = SixfoldAnalysisEngine(database_url=DATABASE_URL)
        
        if IS_PRODUCTION:
            app.logger.info("✓ Connected to PRODUCTION database (Railway)")
        else:
            app.logger.info("✓ Connected to LOCAL database")
    return _engine


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def api_response(data: Any, status: int = 200, message: str = None) -> Response:
    """
    Create a standardized API response.
    
    Parameters:
    -----------
    data : Any
        Response data
    status : int
        HTTP status code
    message : str, optional
        Status message
        
    Returns:
    --------
    Response : Flask JSON response
    """
    response = {
        'status': 'success' if status < 400 else 'error',
        'timestamp': datetime.now().isoformat(),
        'data': data
    }
    if message:
        response['message'] = message
    return jsonify(response), status


def error_response(message: str, status: int = 400) -> Response:
    """
    Create a standardized error response.
    """
    return api_response(None, status, message)


def handle_exceptions(f):
    """
    Decorator to handle exceptions in API endpoints.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            app.logger.error(f"API Error in {f.__name__}: {str(e)}")
            return error_response(f"Internal error: {str(e)}", 500)
    return decorated_function


# =============================================================================
# API ENDPOINTS - Health & Status
# =============================================================================

@app.route('/')
def serve_dashboard():
    """Serve the dashboard HTML file."""
    return render_template('dashboard.html')

@app.route('/health', methods=['GET'])
def health_check_light():
    """
    Lightweight health check for load balancers.
    Does not check database connectivity.
    """
    return "OK", 200


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint.
    
    Returns:
    --------
    JSON response with server status
    """
    return api_response({
        'server': 'running',
        'version': '1.0.0',
        'database': 'connected' if get_engine() else 'disconnected'
    })


@app.route('/api/status', methods=['GET'])
def analysis_status():
    """
    Get the status of the analysis data.
    
    Returns:
    --------
    JSON response with:
    - Last analysis run time
    - Number of queries stored
    - Output file status
    """
    engine = get_engine()
    
    # Check database for stored results
    try:
        sql = "SELECT COUNT(*), MAX(executed_at) FROM first_analysis"
        from sqlalchemy import text
        with engine.engine.connect() as conn:
            result = conn.execute(text(sql)).fetchone()
            query_count = result[0] or 0
            last_run = result[1].isoformat() if result[1] else None
    except Exception:
        query_count = 0
        last_run = None
    
    # Check output files
    network_exists = (NETWORK_DIR / 'd3_network.json').exists()
    dashboard_exists = (DASHBOARD_DIR / 'dashboard_complete.json').exists()
    
    return api_response({
        'stored_queries': query_count,
        'last_analysis_run': last_run,
        'network_data_available': network_exists,
        'dashboard_data_available': dashboard_exists
    })


# =============================================================================
# API ENDPOINTS - Analysis Operations
# =============================================================================

@app.route('/api/analysis/run', methods=['GET', 'POST'])
@handle_exceptions
def run_analysis():
    """
    Run the full analysis pipeline.
    
    This endpoint triggers:
    1. Query execution
    2. Database storage
    3. Network data generation
    4. Dashboard aggregate generation
    
    Query Parameters:
    -----------------
    queries_only : bool
        If true, only run queries (skip network/dashboard)
        
    Returns:
    --------
    JSON response with execution summary
    """
    engine = get_engine()
    
    queries_only = request.args.get('queries_only', 'false').lower() == 'true'
    
    start_time = datetime.now()
    
    if queries_only:
        engine.run_all_queries()
        engine.save_all_results_to_database()
    else:
        engine.run_full_analysis()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    return api_response({
        'queries_executed': len(engine.results),
        'network_edges_generated': len(engine.network_edges),
        'nodes_generated': len(engine.node_attributes),
        'execution_time_seconds': duration,
        'completed_at': end_time.isoformat()
    }, message='Analysis completed successfully')


# =============================================================================
# API ENDPOINTS - Query Results
# =============================================================================

@app.route('/api/results', methods=['GET'])
@handle_exceptions
def list_all_results():
    """
    List all available query results.
    
    Returns:
    --------
    JSON response with list of query IDs and metadata
    """
    engine = get_engine()
    
    from sqlalchemy import text
    sql = """
        SELECT query_id, section, category, description, query_type, 
               row_count, executed_at
        FROM first_analysis
        ORDER BY section, query_id
    """
    
    with engine.engine.connect() as conn:
        results = conn.execute(text(sql)).fetchall()
    
    return api_response([
        {
            'query_id': r[0],
            'section': r[1],
            'category': r[2],
            'description': r[3],
            'query_type': r[4],
            'row_count': r[5],
            'executed_at': r[6].isoformat() if r[6] else None
        }
        for r in results
    ])


@app.route('/api/results/<query_id>', methods=['GET'])
@handle_exceptions
def get_result(query_id: str):
    """
    Get a specific query result.
    
    Path Parameters:
    ----------------
    query_id : str
        Query identifier (e.g., "1.1", "2.3")
        
    Returns:
    --------
    JSON response with query result data
    """
    engine = get_engine()
    result = engine.get_result(query_id)
    
    if result is None:
        return error_response(f"Query result not found: {query_id}", 404)
    
    return api_response(result)


@app.route('/api/sections/<int:section>', methods=['GET'])
@handle_exceptions
def get_section_results(section: int):
    """
    Get all results for a section.
    
    Path Parameters:
    ----------------
    section : int
        Section number (0-8)
        
    Returns:
    --------
    JSON response with all query results for the section
    """
    if section < 0 or section > 8:
        return error_response("Section must be between 0 and 8", 400)
    
    engine = get_engine()
    results = engine.get_section_results(section)
    
    section_names = {
        0: "Overall Summary",
        1: "Foreign Citation",
        2: "International Citation",
        3: "Foreign International Citation",
        4: "Inter-System Citation",
        5: "Member-State Citation",
        6: "Non-Member Citation",
        7: "Comparative Analysis",
        8: "Export-Ready Summary"
    }
    
    return api_response({
        'section': section,
        'section_name': section_names.get(section, f"Section {section}"),
        'queries': results
    })


# =============================================================================
# API ENDPOINTS - Dashboard Data
# =============================================================================

@app.route('/api/dashboard', methods=['GET'])
@handle_exceptions
def get_dashboard():
    """
    Get complete dashboard data.
    
    Returns:
    --------
    JSON response with all dashboard aggregates
    """
    engine = get_engine()
    data = engine.get_dashboard_data()
    
    if not data:
        return error_response("Dashboard data not available. Run analysis first.", 404)
    
    return api_response(data)


@app.route('/api/dashboard/<category>', methods=['GET'])
@handle_exceptions
def get_dashboard_category(category: str):
    """
    Get dashboard data for a specific category.
    
    Path Parameters:
    ----------------
    category : str
        Category key (e.g., "summary_stats", "category_breakdown")
        
    Valid categories:
    - summary_stats
    - category_breakdown  
    - regional_flows
    - comparative
        
    Returns:
    --------
    JSON response with category-specific dashboard data
    """
    engine = get_engine()
    data = engine.get_dashboard_data()
    
    if not data:
        return error_response("Dashboard data not available. Run analysis first.", 404)
    
    if category not in data:
        valid_categories = list(data.keys())
        return error_response(
            f"Invalid category: {category}. Valid: {valid_categories}", 400
        )
    
    return api_response(data[category])


# =============================================================================
# API ENDPOINTS - Network Visualization Data
# =============================================================================

@app.route('/api/network', methods=['GET'])
@handle_exceptions
def get_network():
    """
    Get network visualization data (D3.js format).
    
    Query Parameters:
    -----------------
    min_weight : int
        Minimum edge weight to include (default: 1)
    sixfold_type : str
        Filter by sixfold classification type
        
    Returns:
    --------
    JSON response with nodes and links for D3.js
    """
    engine = get_engine()
    data = engine.get_network_data()
    
    if not data or not data.get('nodes'):
        return error_response("Network data not available. Run analysis first.", 404)
    
    # Apply filters
    min_weight = request.args.get('min_weight', 1, type=int)
    sixfold_type = request.args.get('sixfold_type')
    
    filtered_links = data['links']
    
    if min_weight > 1:
        filtered_links = [l for l in filtered_links if l['value'] >= min_weight]
    
    if sixfold_type:
        filtered_links = [l for l in filtered_links if l['type'] == sixfold_type]
    
    # Filter nodes to only include those in filtered links
    active_nodes = set()
    for link in filtered_links:
        active_nodes.add(link['source'])
        active_nodes.add(link['target'])
    
    filtered_nodes = [n for n in data['nodes'] if n['id'] in active_nodes]
    
    return api_response({
        'nodes': filtered_nodes,
        'links': filtered_links,
        'meta': {
            'total_nodes': len(filtered_nodes),
            'total_links': len(filtered_links),
            'filters_applied': {
                'min_weight': min_weight,
                'sixfold_type': sixfold_type
            }
        }
    })


@app.route('/api/network/nodes', methods=['GET'])
@handle_exceptions
def get_network_nodes():
    """
    Get network node data.
    
    Query Parameters:
    -----------------
    region : str
        Filter by region (Global North, Global South, International)
    sort_by : str
        Sort field (in_degree, out_degree, total_degree)
    limit : int
        Maximum number of nodes to return
        
    Returns:
    --------
    JSON response with node attributes
    """
    network_file = NETWORK_DIR / 'nodes.json'
    if not network_file.exists():
        return error_response("Network data not available. Run analysis first.", 404)
    
    with open(network_file, 'r', encoding='utf-8') as f:
        nodes = json.load(f)
    
    # Convert to list
    node_list = list(nodes.values())
    
    # Apply filters
    region = request.args.get('region')
    if region:
        node_list = [n for n in node_list if n['region'] == region]
    
    # Apply sorting
    sort_by = request.args.get('sort_by', 'total_degree')
    if sort_by in ['in_degree', 'out_degree', 'total_degree']:
        node_list.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
    
    # Apply limit
    limit = request.args.get('limit', type=int)
    if limit:
        node_list = node_list[:limit]
    
    return api_response(node_list)


@app.route('/api/network/edges', methods=['GET'])
@handle_exceptions
def get_network_edges():
    """
    Get network edge data.
    
    Query Parameters:
    -----------------
    source : str
        Filter by source node
    target : str
        Filter by target node
    sixfold_type : str
        Filter by classification type
    min_weight : int
        Minimum edge weight
        
    Returns:
    --------
    JSON response with edge data
    """
    edges_file = NETWORK_DIR / 'edges.json'
    if not edges_file.exists():
        return error_response("Network data not available. Run analysis first.", 404)
    
    with open(edges_file, 'r', encoding='utf-8') as f:
        edges = json.load(f)
    
    # Apply filters
    source = request.args.get('source')
    target = request.args.get('target')
    sixfold_type = request.args.get('sixfold_type')
    min_weight = request.args.get('min_weight', 1, type=int)
    
    if source:
        edges = [e for e in edges if e['source'] == source]
    if target:
        edges = [e for e in edges if e['target'] == target]
    if sixfold_type:
        edges = [e for e in edges if e['sixfold_type'] == sixfold_type]
    if min_weight > 1:
        edges = [e for e in edges if e['weight'] >= min_weight]
    
    return api_response(edges)


# =============================================================================
# API ENDPOINTS - Data Export
# =============================================================================

@app.route('/api/export/csv/<query_id>', methods=['GET'])
@handle_exceptions
def export_query_csv(query_id: str):
    """
    Export a specific query result as CSV.
    
    Path Parameters:
    ----------------
    query_id : str
        Query identifier
        
    Returns:
    --------
    CSV file download
    """
    engine = get_engine()
    result = engine.get_result(query_id)
    
    if result is None:
        return error_response(f"Query result not found: {query_id}", 404)
    
    # Convert to CSV
    data = result.get('data', [])
    if not data:
        return error_response("No data to export", 400)
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=query_{query_id}.csv'
        }
    )


@app.route('/api/export/json/<query_id>', methods=['GET'])
@handle_exceptions
def export_query_json(query_id: str):
    """
    Export a specific query result as JSON.
    
    Path Parameters:
    ----------------
    query_id : str
        Query identifier
        
    Returns:
    --------
    JSON file download
    """
    engine = get_engine()
    result = engine.get_result(query_id)
    
    if result is None:
        return error_response(f"Query result not found: {query_id}", 404)
    
    return Response(
        json.dumps(result, indent=2, ensure_ascii=False),
        mimetype='application/json',
        headers={
            'Content-Disposition': f'attachment; filename=query_{query_id}.json'
        }
    )


@app.route('/api/export/network/<format>', methods=['GET'])
@handle_exceptions
def export_network(format: str):
    """
    Export network data in various formats.
    
    Path Parameters:
    ----------------
    format : str
        Export format: json, csv, gephi
        
    Returns:
    --------
    File download in requested format
    """
    valid_formats = ['json', 'csv', 'gephi']
    if format not in valid_formats:
        return error_response(f"Invalid format. Valid: {valid_formats}", 400)
    
    if format == 'json':
        file_path = NETWORK_DIR / 'd3_network.json'
        if not file_path.exists():
            return error_response("Network data not available", 404)
        return send_file(file_path, as_attachment=True)
    
    elif format == 'csv':
        edges_file = NETWORK_DIR / 'edges.csv'
        if not edges_file.exists():
            return error_response("Network data not available", 404)
        return send_file(edges_file, as_attachment=True)
    
    elif format == 'gephi':
        # Create GEXF format for Gephi
        engine = get_engine()
        data = engine.get_network_data()
        
        if not data or not data.get('nodes'):
            return error_response("Network data not available", 404)
        
        # Generate GEXF XML
        gexf = generate_gexf(data)
        return Response(
            gexf,
            mimetype='application/xml',
            headers={
                'Content-Disposition': 'attachment; filename=network.gexf'
            }
        )


def generate_gexf(data: Dict) -> str:
    """
    Generate GEXF format for Gephi visualization.
    
    Input: D3.js format network data
    Algorithm: Convert to GEXF XML structure
    Output: GEXF XML string
    """
    nodes_xml = []
    for node in data['nodes']:
        nodes_xml.append(
            f'      <node id="{node["id"]}" label="{node["label"]}">\n'
            f'        <attvalues>\n'
            f'          <attvalue for="region" value="{node["region"]}"/>\n'
            f'          <attvalue for="in_degree" value="{node["in_degree"]}"/>\n'
            f'          <attvalue for="out_degree" value="{node["out_degree"]}"/>\n'
            f'        </attvalues>\n'
            f'      </node>'
        )
    
    edges_xml = []
    for i, link in enumerate(data['links']):
        edges_xml.append(
            f'      <edge id="{i}" source="{link["source"]}" target="{link["target"]}" '
            f'weight="{link["value"]}">\n'
            f'        <attvalues>\n'
            f'          <attvalue for="type" value="{link["type"]}"/>\n'
            f'        </attvalues>\n'
            f'      </edge>'
        )
    
    gexf = f'''<?xml version="1.0" encoding="UTF-8"?>
<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">
  <meta lastmodifieddate="{datetime.now().strftime('%Y-%m-%d')}">
    <creator>Sixfold Citation Analysis</creator>
    <description>Climate Litigation Citation Network</description>
  </meta>
  <graph mode="static" defaultedgetype="directed">
    <attributes class="node">
      <attribute id="region" title="Region" type="string"/>
      <attribute id="in_degree" title="In Degree" type="integer"/>
      <attribute id="out_degree" title="Out Degree" type="integer"/>
    </attributes>
    <attributes class="edge">
      <attribute id="type" title="Sixfold Type" type="string"/>
    </attributes>
    <nodes>
{chr(10).join(nodes_xml)}
    </nodes>
    <edges>
{chr(10).join(edges_xml)}
    </edges>
  </graph>
</gexf>'''
    
    return gexf


@app.route('/api/export/dashboard', methods=['GET'])
@handle_exceptions
def export_dashboard():
    """
    Export complete dashboard data as JSON.
    
    Returns:
    --------
    JSON file download
    """
    file_path = DASHBOARD_DIR / 'dashboard_complete.json'
    if not file_path.exists():
        return error_response("Dashboard data not available. Run analysis first.", 404)
    
    return send_file(file_path, as_attachment=True)


# =============================================================================
# API ENDPOINTS - Custom Queries
# =============================================================================

@app.route('/api/custom/flow', methods=['GET'])
@handle_exceptions
def custom_flow_query():
    """
    Custom endpoint for flow analysis.
    
    Query Parameters:
    -----------------
    from_region : str
        Source region filter
    to_region : str
        Target region filter
    sixfold_type : str
        Classification type filter
        
    Returns:
    --------
    JSON response with filtered flow data
    """
    engine = get_engine()
    
    from_region = request.args.get('from_region')
    to_region = request.args.get('to_region')
    sixfold_type = request.args.get('sixfold_type')
    
    # Build dynamic SQL
    conditions = []
    params = {}
    
    if from_region:
        conditions.append("source_region = :from_region")
        params['from_region'] = from_region
    if to_region:
        conditions.append("case_law_region = :to_region")
        params['to_region'] = to_region
    if sixfold_type:
        conditions.append("sixfold_type = :sixfold_type")
        params['sixfold_type'] = sixfold_type
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    sql = f"""
        SELECT 
            source_jurisdiction,
            source_region,
            case_law_origin,
            case_law_region,
            sixfold_type,
            COUNT(*) as citation_count
        FROM citation_sixfold_classification
        WHERE {where_clause}
        GROUP BY source_jurisdiction, source_region, 
                 case_law_origin, case_law_region, sixfold_type
        ORDER BY citation_count DESC
        LIMIT 100
    """
    
    from sqlalchemy import text
    with engine.engine.connect() as conn:
        results = conn.execute(text(sql), params).fetchall()
    
    return api_response([
        {
            'source_jurisdiction': r[0],
            'source_region': r[1],
            'case_law_origin': r[2],
            'case_law_region': r[3],
            'sixfold_type': r[4],
            'citation_count': r[5]
        }
        for r in results
    ])


@app.route('/api/custom/top-cases', methods=['GET'])
@handle_exceptions
def custom_top_cases():
    """
    Custom endpoint for top cited cases with flexible filtering.
    
    Query Parameters:
    -----------------
    sixfold_type : str
        Classification type filter
    region : str
        Case law origin region filter
    limit : int
        Number of results (default: 20)
        
    Returns:
    --------
    JSON response with top cited cases
    """
    engine = get_engine()
    
    sixfold_type = request.args.get('sixfold_type')
    region = request.args.get('region')
    limit = request.args.get('limit', 20, type=int)
    
    conditions = []
    params = {'limit': min(limit, 100)}
    
    if sixfold_type:
        conditions.append("sixfold_type = :sixfold_type")
        params['sixfold_type'] = sixfold_type
    if region:
        conditions.append("case_law_region = :region")
        params['region'] = region
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    sql = f"""
        SELECT 
            case_name,
            case_law_origin,
            case_law_region,
            sixfold_type,
            COUNT(*) as citation_count,
            COUNT(DISTINCT source_jurisdiction) as citing_jurisdictions
        FROM citation_sixfold_classification
        WHERE {where_clause}
        GROUP BY case_name, case_law_origin, case_law_region, sixfold_type
        ORDER BY citation_count DESC
        LIMIT :limit
    """
    
    from sqlalchemy import text
    with engine.engine.connect() as conn:
        results = conn.execute(text(sql), params).fetchall()
    
    return api_response([
        {
            'case_name': r[0],
            'case_law_origin': r[1],
            'case_law_region': r[2],
            'sixfold_type': r[3],
            'citation_count': r[4],
            'citing_jurisdictions': r[5]
        }
        for r in results
    ])


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.errorhandler(404)
def not_found(error):
    return error_response("Endpoint not found", 404)


@app.errorhandler(500)
def internal_error(error):
    return error_response("Internal server error", 500)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """
    Run the Flask development server.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Sixfold Citation Classification API Server'
    )
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='Host to bind to'
    )
    parser.add_argument(
        '--port',
        default=5000,
        type=int,
        help='Port to bind to'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )
    
    args = parser.parse_args()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║    SIXFOLD CITATION CLASSIFICATION - API SERVER              ║
╠══════════════════════════════════════════════════════════════╣
║  Server URL: http://{args.host}:{args.port}                        ║
║  API Docs:   http://{args.host}:{args.port}/api/health             ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
