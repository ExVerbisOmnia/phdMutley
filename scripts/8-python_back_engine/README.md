# Sixfold Citation Classification - Analysis Engine

## Overview

This package provides a comprehensive analysis system for the sixfold citation classification in climate litigation research. It includes:

1. **Analysis Engine** (`sixfold_analysis_engine.py`) - Core query execution and data processing
2. **REST API Server** (`api_server.py`) - Backend for frontend applications
3. **Dashboard Frontend** (`dashboard.html`) - Sample visualization interface
4. **SQL Scripts** - Database setup and view creation

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (HTML/JS)                          │
│                      dashboard.html                             │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/REST
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Server (Flask)                           │
│                     api_server.py                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Analysis Engine (SQLAlchemy)                   │
│                sixfold_analysis_engine.py                       │
├─────────────────────────────────────────────────────────────────┤
│  - Query Execution                                              │
│  - Network Data Generation                                      │
│  - Dashboard Aggregates                                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
           ┌─────────────────┴─────────────────┐
           ▼                                   ▼
┌──────────────────────┐          ┌──────────────────────┐
│   PostgreSQL DB      │          │   JSON/CSV Files     │
│ - first_analysis     │          │ - Network data       │
│ - citation_sixfold_  │          │ - Dashboard data     │
│   classification     │          │                      │
└──────────────────────┘          └──────────────────────┘
```

## Prerequisites

1. **PostgreSQL 18** with the climate_litigation database
2. **Python 3.11+**
3. The `citation_sixfold_classification` view must exist (run the SQL scripts first)

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt --break-system-packages
```

### 2. Run SQL Setup Scripts

Before running the analysis, ensure the database views are created:

```bash
# Create the international court jurisdiction table
psql -d climate_litigation -f international_court_jurisdiction.sql

# Create the sixfold classification view
psql -d climate_litigation -f sixfold_classification_complete.sql
```

### 3. Configure Database Connection

Set the `DATABASE_URL` environment variable:

```bash
# Linux/Mac
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/climate_litigation"

# Windows PowerShell
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/climate_litigation"
```

Or modify the default in `sixfold_analysis_engine.py`.

## Usage

### Running the Full Analysis

```bash
python sixfold_analysis_engine.py
```

This will:
1. Execute all 35 analysis queries
2. Create and populate the `first_analysis` table
3. Generate network data files in `./analysis_output/network_data/`
4. Generate dashboard aggregates in `./analysis_output/dashboard_data/`

#### Command-Line Options

```bash
# Run queries only (skip network/dashboard generation)
python sixfold_analysis_engine.py --queries-only

# Generate network data only
python sixfold_analysis_engine.py --network-only

# Generate dashboard data only
python sixfold_analysis_engine.py --dashboard-only

# Custom output directory
python sixfold_analysis_engine.py --output-dir /path/to/output

# Verbose logging
python sixfold_analysis_engine.py -v
```

### Starting the API Server

```bash
# Development mode
python api_server.py --debug

# Production mode (with Gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 api_server:app
```

### Opening the Dashboard

1. Start the API server (see above)
2. Open `dashboard.html` in a web browser
3. The dashboard will automatically connect to the API at `http://127.0.0.1:5000`

## API Endpoints

### Health & Status

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/status` | GET | Analysis status |

### Analysis Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analysis/run` | GET/POST | Run full analysis |

### Query Results

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/results` | GET | List all query results |
| `/api/results/<query_id>` | GET | Get specific result (e.g., `/api/results/1.1`) |
| `/api/sections/<section>` | GET | Get all results for a section (0-8) |

### Dashboard Data

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard` | GET | Complete dashboard data |
| `/api/dashboard/<category>` | GET | Specific category data |

### Network Visualization

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/network` | GET | D3.js format network data |
| `/api/network/nodes` | GET | Node attributes |
| `/api/network/edges` | GET | Edge data |

Query parameters for `/api/network`:
- `min_weight` (int): Minimum edge weight
- `sixfold_type` (str): Filter by classification type

### Data Export

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/export/csv/<query_id>` | GET | Export query as CSV |
| `/api/export/json/<query_id>` | GET | Export query as JSON |
| `/api/export/network/<format>` | GET | Export network (json/csv/gephi) |
| `/api/export/dashboard` | GET | Export dashboard JSON |

### Custom Queries

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/custom/flow` | GET | Filtered flow analysis |
| `/api/custom/top-cases` | GET | Top cited cases with filters |

## Output Files

### Database Table: `first_analysis`

Stores all analysis query results with the following schema:

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `query_id` | VARCHAR(20) | Query identifier (e.g., "1.1") |
| `section` | INTEGER | Section number (0-8) |
| `category` | VARCHAR(100) | Category name |
| `description` | TEXT | Human-readable description |
| `query_type` | VARCHAR(50) | Query type (overview, top_n, etc.) |
| `result_data` | JSONB | Query results as JSON |
| `row_count` | INTEGER | Number of rows |
| `executed_at` | TIMESTAMP | Execution timestamp |

### Network Data Files (`./analysis_output/network_data/`)

| File | Format | Description |
|------|--------|-------------|
| `edges.json` | JSON | All edges with attributes |
| `edges.csv` | CSV | Edges for spreadsheet tools |
| `nodes.json` | JSON | Node attributes |
| `nodes.csv` | CSV | Nodes for spreadsheet tools |
| `d3_network.json` | JSON | D3.js-ready format |

### Dashboard Data Files (`./analysis_output/dashboard_data/`)

| File | Format | Description |
|------|--------|-------------|
| `summary_stats.json` | JSON | High-level statistics |
| `category_breakdown.json` | JSON | By sixfold category |
| `regional_flows.json` | JSON | North-South flow data |
| `comparative.json` | JSON | Cross-category analysis |
| `dashboard_complete.json` | JSON | Complete bundle |

## Query Reference

### Section 0: Overall Summary
- **0.1**: Total citations by sixfold classification
- **0.2**: Summary by direction

### Section 1: Foreign Citation
- **1.1**: Overview
- **1.2**: Regional flow matrix (N→N, N→S, S→N, S→S)
- **1.3**: Top 10 source jurisdictions
- **1.4**: Top 10 cited jurisdictions
- **1.5**: Top 10 most cited cases

### Section 2: International Citation
- **2.1**: Overview
- **2.2**: By source region
- **2.3**: Top source jurisdictions
- **2.4**: Most cited tribunals
- **2.5**: Top 10 cases

### Section 3: Foreign International Citation
- **3.1**: Overview
- **3.2**: By source region
- **3.3**: Top source jurisdictions
- **3.4**: Most cited tribunals
- **3.5**: Top 10 cases
- **3.6**: Cross-system citations

### Section 4: Inter-System Citation
- **4.1**: Overview
- **4.2**: Tribunal-to-tribunal flows
- **4.3**: Most active citing tribunals
- **4.4**: Most cited tribunals
- **4.5**: Top 10 cases

### Section 5: Member-State Citation
- **5.1**: Overview
- **5.2**: By cited region
- **5.3**: Top source tribunals
- **5.4**: Most cited jurisdictions
- **5.5**: Top 10 cases

### Section 6: Non-Member Citation
- **6.1**: Overview
- **6.2**: By cited region
- **6.3**: Top source tribunals
- **6.4**: Most cited jurisdictions
- **6.5**: Top 10 cases
- **6.6**: Cross-regional citations

### Section 7: Comparative Analysis
- **7.1**: Decisions by number of types
- **7.2**: North-South asymmetry
- **7.3**: Global South engagement
- **7.4**: Top 10 overall

### Section 8: Export Summary
- **8.1**: Final summary table (thesis-ready)

## Extending the System

### Adding New Queries

1. Add a new method in `SixfoldAnalysisEngine`:

```python
def query_X_Y_description(self) -> AnalysisResult:
    """Query X.Y: Description."""
    sql = """
        SELECT ...
        FROM citation_sixfold_classification
        WHERE ...
    """
    data = self._execute_query(sql)
    
    return AnalysisResult(
        query_id="X.Y",
        section=X,
        category="Category Name",
        description="Human-readable description",
        query_type="overview",  # or: top_n, flow_matrix, etc.
        data=data,
        row_count=len(data),
        executed_at=datetime.now()
    )
```

2. Add the call to `run_all_queries()`:

```python
self.results['X.Y'] = self.query_X_Y_description()
```

### Adding New API Endpoints

In `api_server.py`:

```python
@app.route('/api/custom/my-endpoint', methods=['GET'])
@handle_exceptions
def my_custom_endpoint():
    engine = get_engine()
    # Your logic here
    return api_response(data)
```

## Troubleshooting

### Common Issues

1. **"View does not exist" error**
   - Run the SQL setup scripts first
   - Ensure `international_court_jurisdiction.sql` runs before `sixfold_classification_complete.sql`

2. **API Connection Failed**
   - Check if the API server is running
   - Verify the port is not blocked by firewall
   - Ensure CORS is configured for your frontend origin

3. **Empty Results**
   - Run the full analysis first: `python sixfold_analysis_engine.py`
   - Check if the source data is populated in `citation_extraction_phased`

4. **Performance Issues**
   - Increase `pool_size` in engine configuration for high concurrency
   - Add database indexes if queries are slow
   - Use `min_weight` filter to reduce network complexity

## License

This software is part of the PhD research project on transnational climate litigation.

## Author

Gustavo - University of São Paulo Law School
With assistance from Claude (Anthropic)
