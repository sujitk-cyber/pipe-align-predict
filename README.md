# ILI Pipeline Alignment & Corrosion Growth Prediction

Automated alignment of multi-run ILI (In-Line Inspection) datasets with anomaly matching, corrosion growth rate calculation, severity scoring, and reporting — all from the command line.

## Quick Start

```bash
pip install -r requirements.txt

python run_pipeline.py ILIDataV2.xlsx \
    --sheet_a 2015 --sheet_b 2022 --years 7 \
    --output_dir outputs/
```

## Installation

Requires **Python 3.10+**.

```bash
git clone https://github.com/sujitk-cyber/pipe-align-predict.git
cd pipe-align-predict
pip install -r requirements.txt
```

### Dependencies

| Package | Purpose |
|---------|---------|
| numpy | Numerical operations |
| pandas | Data manipulation |
| scipy | Hungarian matching, curve fitting |
| openpyxl | Excel file reading |
| plotly | Interactive charts (optional, for HTML reports) |
| jinja2 | HTML report templates (optional) |
| scikit-learn | DBSCAN clustering (optional) |
| pytest | Testing |

## Web Application

WeldWarp includes a modern web interface for interactive analysis.

### Prerequisites

- **Backend**: Python 3.10+
- **Frontend**: Node.js 18+

### Running Locally

1. **Start the Backend API**:

   ```bash
   cd web_backend
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```
   Server runs at `http://127.0.0.1:8000`.

2. **Start the Frontend UI**:

   ```bash
   cd web_frontend
   npm install
   npm run dev
   ```
   App runs at `http://localhost:3000`.

### Features

- **Upload Interface**: Drag-and-drop ILI files (Excel/CSV).
- **Job Management**: Asynchronous pipeline execution.
- **Results Dashboard**:
    - Interactive matching statistics charts.
    - Growth rate distributions.
    - Top critical anomalies list.

## Usage

### Basic — Two Sheets from One Excel File

```bash
python run_pipeline.py ILIDataV2.xlsx --sheet_a 2015 --sheet_b 2022 --years 7
```

### Two Separate CSV Files

```bash
python run_pipeline.py run1.csv run2.csv --years 10
```

### Full Options

```bash
python run_pipeline.py ILIDataV2.xlsx \
    --sheet_a 2015 --sheet_b 2022 --years 7 \
    --dist_tol 15 --clock_tol 20 --cost_thresh 20 \
    --critical_depth 80 --forecast_years 5 \
    --html_report \
    --clustering_epsilon 50 --clustering_mode 1d \
    --output_dir results/
```

## CLI Parameter Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| `file_a` | *(required)* | Path to Run A data file (Excel or CSV) |
| `file_b` | *(optional)* | Path to Run B file. Omit if using sheets from file_a |
| `--sheet_a` | `0` | Sheet name or index for Run A |
| `--sheet_b` | `1` | Sheet name or index for Run B |
| `--years` | *(required)* | Years between Run A and Run B |
| `--dist_tol` | `10.0` | Distance tolerance (ft) for matching candidates |
| `--clock_tol` | `15.0` | Clock position tolerance (degrees) |
| `--cost_thresh` | `15.0` | Cost threshold — above this, match is flagged UNCERTAIN |
| `--critical_depth` | `80.0` | Critical depth % WT for remaining life calculation |
| `--forecast_years` | `5` | Forecast horizon (years) for depth projection |
| `--html_report` | off | Generate interactive HTML report (requires plotly & jinja2) |
| `--clustering_epsilon` | *(off)* | DBSCAN epsilon (ft). Omit to skip clustering |
| `--clustering_mode` | `1d` | Clustering mode: `1d` (distance) or `2d` (distance + clock) |
| `--output_dir` / `-o` | `outputs/` | Output directory |
| `--verbose` / `-v` | off | Enable debug logging |
| `--quiet` / `-q` | off | Suppress info logging |

## How It Works

### 1. Ingest & Column Mapping (`src/io.py`)

Reads Excel or CSV files with vendor-specific column names. An auto-detection routine inspects column headers and selects the best mapping configuration (supports Rosen 2007, Baker Hughes 2015, Entegra 2022 formats). All data is transformed into a canonical schema.

### 2. Piecewise Linear Alignment (`src/alignment.py`)

Fixed pipeline features (girth welds, valves, tees, bends) are identified as **control points**. Control points are matched between runs by joint number (preferred) or ordered sequence with spacing validation.

For each consecutive pair of matched control points:
```
scale = (a1 - a0) / (b1 - b0)
shift = a0 - scale * b0
corrected_distance_B = scale * distance_B + shift
```

Falls back to global constant offset if fewer than 2 control points match.

### 3. Segment-wise Hungarian Matching (`src/matching.py`)

The pipeline is divided into segments between control points. Within each segment:

1. **Candidate gating**: Filters pairs by distance tolerance, clock tolerance, feature type compatibility, and orientation match.
2. **Cost function**: `w_dist × Δdist + w_clock × Δclock + w_depth × Δdepth + w_size × Δsize + type_penalty`
3. **Hungarian algorithm** (`scipy.optimize.linear_sum_assignment`): Optimal one-to-one assignment.
4. **Thresholding**: Matches above `cost_thresh` are flagged `UNCERTAIN`. Unmatched anomalies are labelled `MISSING` (Run A only) or `NEW` (Run B only).

### 4. Growth Analysis (`src/growth.py`)

- **Growth rates**: `depth_growth = (depth_B − depth_A) / years`
- **Remaining life**: `(critical_depth − depth_B) / growth_rate`
- **Severity scoring**: Weighted combination of growth rate (40%), current depth (35%), and remaining life urgency (25%), normalised to 0–100.
- **Forecasting**: Linear extrapolation of future depth.
- **Non-linear models** (3+ runs): Exponential, power-law, and polynomial fits with AIC/BIC model selection.

### 5. Clustering (`src/clustering.py`, optional)

DBSCAN-based spatial clustering of anomalies to identify interaction zones. Supports 1D (distance only) and 2D (distance + clock) modes.

## Output Files

| File | Description |
|------|-------------|
| `matched_results.csv` | One row per matched anomaly pair. Includes Run A/B fields, corrected distance, deltas, growth rates, severity score, status (MATCHED/UNCERTAIN) |
| `missing_anomalies.csv` | Run A anomalies with no match in Run B (status = MISSING) |
| `new_anomalies.csv` | Run B anomalies with no match in Run A (status = NEW) |
| `growth_summary.csv` | Mean/median/max growth rates grouped by feature type |
| `dig_list.csv` | Top-50 most severe anomalies ranked by severity score |
| `alignment_report.json` | Structured report: control points, segment transforms, residuals, matching stats, top-10 severity |
| `clusters_summary.csv` | Per-cluster metrics (only if `--clustering_epsilon` is set) |
| `report.html` | Interactive HTML report with Plotly charts (only if `--html_report` is set) |

## Troubleshooting

### "No control points could be matched"
The alignment requires at least girth welds (or valves/tees/bends) to be present in both runs. Check that your data contains rows with event descriptions like "Girth Weld", "Valve", etc.

### Wrong sheet selected
Use `--sheet_a` and `--sheet_b` with the exact sheet name as it appears in Excel (e.g., `--sheet_a 2015 --sheet_b 2022`). Numeric values 0-9 are treated as sheet indices.

### Column mapping not detected
The auto-detection covers Rosen, Baker Hughes, and Entegra formats. If your vendor uses different column names, add a new mapping config in `src/io.py` → `MAPPING_CONFIGS`.

### All anomalies showing as MISSING/NEW
Try increasing `--dist_tol` (default 10 ft) or `--clock_tol` (default 15 deg). Large odometer drift between runs may require wider tolerances.

### Negative growth rates
Negative depth growth is flagged as a possible measurement error. These anomalies are included in outputs with `negative_growth_flag = True` but their remaining life is set to infinity.

### Excel format issues
Ensure the Excel file is saved as `.xlsx` (not `.xls`). Merged cells, hidden rows, and formatting may cause issues — export to a clean worksheet first.

## Testing

```bash
python -m pytest tests/ -v
python -m pytest tests/ --cov=src --cov-report=term-missing
```

## Project Structure

```
run_pipeline.py          # CLI entry point
src/
  io.py                  # Data ingestion and column mapping
  preprocess.py          # Clock parsing, feature type normalisation
  alignment.py           # Piecewise linear distance alignment
  matching.py            # Segment-wise Hungarian matching
  growth.py              # Growth rates, severity, forecasting
  clustering.py          # DBSCAN anomaly clustering
  reporting.py           # CSV/JSON output generation
  visualization.py       # Plotly chart generation
  html_report.py         # HTML report with embedded charts
tests/                   # Comprehensive pytest suite
ili_alignment.py         # Legacy standalone implementation
web_backend/             # FastAPI Backend
web_frontend/            # Next.js Frontend
```

## License

See repository for license details.
