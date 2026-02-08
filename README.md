# WeldWarp — ILI Pipeline Integrity Platform

Automated alignment of multi-run ILI (In-Line Inspection) datasets with anomaly matching, corrosion growth rate calculation, severity scoring, and reporting. Includes a full web application with OAuth authentication and role-based access control.

## Quick Start

```bash
# CLI
pip install -r requirements.txt
python run_pipeline.py data.xlsx --sheet_a 2015 --sheet_b 2022 --years 7

# Web App
cd web_backend && pip install -r requirements.txt
uvicorn web_backend.main:app --host 0.0.0.0 --port 8000

cd web_frontend && npm install && npm run dev
# Open http://localhost:3000
```

## Web Application

### Features

- **Apple Liquid Glass UI** — Dark mode with translucent frosted glass panels, mesh gradient backgrounds, and an interactive cursor glow effect
- **Drag & Drop Upload** — Upload ILI Excel/CSV files with automatic multi-sheet detection
- **Sheet Selection** — When uploading a multi-sheet Excel file, automatically detects data sheets and lets you pick which runs to compare
- **Async Pipeline** — Jobs run in the background with real-time status polling
- **Results Dashboard** — KPI cards, matching overview charts, confidence distribution, top critical anomalies
- **Growth & Risk Analysis** — Area charts of growth trends along the pipeline, severity-ranked risk segments
- **Matching Review** — Paginated, sortable, filterable table of all matched anomalies with detail panels
- **File Downloads** — Export all pipeline output files (CSV, JSON, HTML report)
- **OAuth Authentication** — Sign in with Google or GitHub
- **Role-Based Access** — Admin, Engineer, and Viewer roles with different permissions
- **Job Ownership** — Engineers see their own jobs + shared jobs; Admins see all; Viewers see only shared jobs

### Roles & Permissions

| | Admin | Engineer | Viewer |
|---|---|---|---|
| View jobs | All | Own + shared | Shared only |
| Upload & run | Yes | Yes | No |
| Delete jobs | Any | Own only | No |
| Share jobs | Any | Own only | No |
| Manage users | Yes | No | No |

The first user to sign in automatically becomes Admin.

### Prerequisites

- **Python 3.10+** with venv
- **Node.js 18+**
- OAuth credentials from [Google Cloud Console](https://console.cloud.google.com/apis/credentials) and/or [GitHub Developer Settings](https://github.com/settings/developers)

### Setup

1. **Backend**:
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   pip install -r web_backend/requirements.txt
   ```

2. **Frontend**:
   ```bash
   cd web_frontend
   npm install
   ```

3. **OAuth Configuration** — Edit `web_frontend/.env.local`:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   NEXTAUTH_URL=http://localhost:3000
   NEXTAUTH_SECRET=<generate with: openssl rand -base64 32>

   # Google OAuth
   GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-<your-secret>

   # GitHub OAuth
   GITHUB_ID=<your-client-id>
   GITHUB_SECRET=<your-client-secret>
   ```

   **Google**: Create OAuth 2.0 Client ID → Authorized redirect URI: `http://localhost:3000/api/auth/callback/google`

   **GitHub**: Register OAuth App → Authorization callback URL: `http://localhost:3000/api/auth/callback/github`

4. **Run**:
   ```bash
   # Terminal 1 — Backend
   uvicorn web_backend.main:app --host 0.0.0.0 --port 8000

   # Terminal 2 — Frontend
   cd web_frontend && npm run dev
   ```

   Open http://localhost:3000, sign in, upload an xlsx file, and run the pipeline.

## CLI Usage

### Two Sheets from One Excel File

```bash
python run_pipeline.py data.xlsx --sheet_a 2015 --sheet_b 2022 --years 7
```

### Two Separate CSV Files

```bash
python run_pipeline.py run1.csv run2.csv --years 10
```

### Full Options

```bash
python run_pipeline.py data.xlsx \
    --sheet_a 2015 --sheet_b 2022 --years 7 \
    --dist_tol 15 --clock_tol 20 --cost_thresh 20 \
    --critical_depth 80 --forecast_years 5 \
    --html_report \
    --clustering_epsilon 50 --clustering_mode 1d \
    --output_dir results/
```

## CLI Parameters

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
| `--critical_depth` | `80.0` | Critical depth % WT for remaining life |
| `--forecast_years` | `5` | Forecast horizon (years) for depth projection |
| `--html_report` | off | Generate interactive HTML report |
| `--clustering_epsilon` | *(off)* | DBSCAN epsilon (ft). Omit to skip clustering |
| `--clustering_mode` | `1d` | Clustering: `1d` (distance) or `2d` (distance + clock) |
| `--output_dir` | `outputs/` | Output directory |
| `--verbose` | off | Debug logging |

## Algorithms & Mathematics

### 1. Data Ingestion & Column Mapping (`src/io.py`)

Reads Excel/CSV with vendor-specific column names. An auto-detection system scores each known mapping config against the file's headers and picks the best match. Supports Rosen, Baker Hughes, Entegra, and a broad generic config. If all configs score poorly (score <= 2 and no distance column found), a fuzzy substring fallback scans column names for common patterns like `dist`, `odometer`, `depth`, `clock`, etc.

All data is normalised into a canonical schema: `distance`, `clock_deg`, `depth_percent`, `feature_type_norm`, `orientation`, `length`, `width`, `wall_thickness`.

### 2. Clock Position Conversion (`src/preprocess.py`)

Clock positions (e.g., "3:00", "9:30") are converted to degrees on a 360-degree circle:

```
hours = hours mod 12
degrees = hours × 30
```

Convention: 12:00 (top-dead-centre) = 0°, increasing clockwise. So 3:00 = 90°, 6:00 = 180°, 9:00 = 270°.

Angular distance between two clock positions uses the shortest arc:

```
diff = |deg_A - deg_B| mod 360
clock_distance = min(diff, 360 - diff)
```

This gives a range of 0–180°.

### 3. Piecewise Linear Alignment (`src/alignment.py`)

ILI tools measure distance from a launcher using odometer wheels. Between runs, the odometer readings drift due to wheel slip, tool speed variation, and pipeline modifications. Alignment corrects Run B distances into Run A's coordinate system.

**Control Point Identification**: Fixed pipeline features (girth welds, valves, tees, bends, flanges) are extracted from both runs. These are physical landmarks that don't move between inspections.

**Control Point Matching**: Two strategies are attempted:

1. **Joint number matching** (preferred): Direct join on joint number column.
2. **Sequence matching** (fallback): Ordered matching with spacing validation. A pair is accepted only if the inter-weld spacing differs by less than 20%:

```
diff_pct = |spacing_B - spacing_A| / spacing_A
accepted if diff_pct < 0.20
```

**Segment Transform**: For each consecutive pair of matched control points (a₀, a₁) and (b₀, b₁):

```
scale = (a₁ - a₀) / (b₁ - b₀)
shift = a₀ - scale × b₀
```

If the Run B span is near-zero (`|b₁ - b₀| < 1e-9`), fall back to:

```
scale = 1.0
shift = a₀ - b₀
```

**Applying the Transform**: Each Run B anomaly within a segment is corrected:

```
corrected_distance_B = scale × distance_B + shift
```

**Alignment Residuals**: For matched control points, the residual measures alignment quality:

```
residual = corrected_distance_B - distance_A
```

Mean and max residuals are reported. A perfect alignment gives residuals near zero.

**Fallback**: If fewer than 2 control points match, a global constant offset is computed from the single matched pair.

### 4. Segment-wise Hungarian Matching (`src/matching.py`)

The pipeline is divided into segments between consecutive matched control points. Within each segment, anomalies are matched optimally.

**Candidate Gating**: A pair (A_i, B_j) is only considered if:

- `|dist_A - dist_B| ≤ dist_tol` (default 10 ft)
- `clock_distance(A, B) ≤ clock_tol` (default 15°)
- Feature types are compatible (same type or explicitly mapped, e.g., `metal_loss ↔ cluster`)
- Orientation matches (if both are known)

Infeasible pairs get a cost of `1,000,000`.

**Cost Function**: For each feasible pair:

```
cost = w_dist × |Δdist| + w_clock × |Δclock| + w_depth × |Δdepth| + w_size × Δsize + type_penalty
```

Where:

| Weight | Default | Component |
|--------|---------|-----------|
| `w_dist` | 1.0 | Distance difference (ft) |
| `w_clock` | 0.5 | Clock angular difference (°) |
| `w_depth` | 0.1 | Depth percent difference |
| `w_size` | 0.05 | `|Δlength| + |Δwidth|` (inches) |
| `type_penalty` | 10.0 | Added if types differ but are compatible |

**Hungarian Algorithm**: The cost matrix is solved with `scipy.optimize.linear_sum_assignment` to find the minimum-cost one-to-one assignment. This guarantees the globally optimal matching within each segment.

**Thresholding**: Matches with `cost > cost_thresh` (default 15.0) are flagged `UNCERTAIN`. Unmatched anomalies become `MISSING` (Run A only) or `NEW` (Run B only).

**Match Probability** (Gaussian error model): Estimates how likely a match is correct:

```
exponent = (Δdist / σ_d)² + (Δclock / σ_c)² + (Δdepth / σ_depth)²
probability = exp(-exponent) × type_match × orient_match
```

Default sigmas: `σ_d = 5.0 ft`, `σ_c = 15.0°`, `σ_depth = 10.0%`.

**Match Confidence** (sigmoid model): Combines cost, margin to second-best, and candidate density:

```
margin = second_best_cost - best_cost    (or 20.0 if no second candidate)
z = α × (-cost) + β × margin - γ × candidate_count
confidence = 1 / (1 + exp(-z))
```

Default parameters: `α = 0.3`, `β = 0.5`, `γ = 0.05`.

Confidence labels:
- **High**: confidence ≥ 0.7
- **Medium**: confidence ≥ 0.4
- **Low**: confidence < 0.4

### 5. Growth Analysis (`src/growth.py`)

**Growth Rates** (linear, for 2-run comparison):

```
depth_growth (%WT/yr) = (depth_B - depth_A) / years_between
length_growth (in/yr) = (length_B - length_A) / years_between
width_growth (in/yr)  = (width_B - width_A) / years_between
```

Negative growth rates are flagged as potential measurement errors (`negative_growth_flag = True`).

**Remaining Life Estimation**:

```
remaining_life (yr) = (critical_depth - depth_B) / growth_rate
```

Rules:
- If `growth_rate ≤ 0` → `∞` (not growing)
- If `depth_B ≥ critical_depth` → `0` (already critical)
- Default critical depth: 80% wall thickness

**Severity Scoring** (0–100 scale):

```
score = [w_growth × norm(growth_rate) + w_depth × norm(depth_B) + w_remaining × norm(1/remaining_life)] × 100
```

| Weight | Value | Factor |
|--------|-------|--------|
| `w_growth` | 0.40 | How fast the anomaly is growing |
| `w_depth` | 0.35 | How deep it already is |
| `w_remaining` | 0.25 | Urgency (inverse remaining life) |

Each factor is min-max normalised across all anomalies:

```
norm(x) = (x - min) / (max - min)
```

Higher score = more urgent. Anomalies are ranked by severity to produce the dig list.

**Forecasting** (linear extrapolation):

```
projected_depth = depth_B + growth_rate × forecast_years
```

Only applied for positive growth rates. Negative-growth anomalies keep their current depth.

**Acceleration Detection** (for multi-run data):

Compares early-period vs late-period growth rates:

```
change_pct = ((rate_late - rate_early) / rate_early) × 100
```

Flagged as accelerating if `change_pct > 50%`.

**Non-Linear Growth Models** (for 3+ data points across multiple runs):

Four models are fit via `scipy.optimize.curve_fit`:

| Model | Formula | Parameters |
|-------|---------|------------|
| Linear | `depth = a + b·t` | a, b |
| Exponential | `depth = a · exp(b·t)` | a, b |
| Power law | `depth = a · t^b` | a, b |
| Quadratic | `depth = a + b·t + c·t²` | a, b, c |

**Model Selection** uses AIC and BIC:

```
AIC = n × ln(RSS/n) + 2k
BIC = n × ln(RSS/n) + k × ln(n)
```

Where `n` = number of data points, `k` = number of parameters, `RSS = Σ(observed - predicted)²`.

The model with the lowest AIC is selected as the best fit for each anomaly's growth trajectory.

### 6. DBSCAN Clustering (`src/clustering.py`, optional)

Groups nearby anomalies into interaction zones using density-based spatial clustering.

**Parameters**:
- `epsilon` (default 50 ft) — maximum distance between two anomalies to be in the same cluster
- `min_samples` (default 2) — minimum anomalies to form a cluster

**1D mode**: Clusters on distance only.

**2D mode**: Clusters on distance + clock position. Clock is normalised to the same scale as distance:

```
clock_normalised = (clock_deg / 360) × epsilon
```

This ensures both dimensions contribute equally to the Euclidean distance metric.

**Cluster Metrics**:
- Centroid distance (mean odometer position)
- Span (max distance - min distance)
- Average depth
- Total metal loss area (`Σ length × width`)
- Mean growth rate

## Output Files

| File | Description |
|------|-------------|
| `matched_results.csv` | Matched anomaly pairs with growth rates, severity scores, confidence labels |
| `missing_anomalies.csv` | Run A anomalies with no Run B match |
| `new_anomalies.csv` | Run B anomalies with no Run A match |
| `growth_summary.csv` | Growth rates grouped by feature type |
| `dig_list.csv` | Top 50 most severe anomalies ranked by severity score |
| `alignment_report.json` | Structured report with control points, segment transforms, residuals, matching stats, top-10 severity |
| `clusters_summary.csv` | Per-cluster metrics (only if `--clustering_epsilon` is set) |
| `report.html` | Interactive HTML report with Plotly charts (only if `--html_report`) |

## Auto-Detection

The platform auto-detects column mappings for common ILI vendors:

- **Rosen** (2007 format) — `log dist. [ft]`, `o'clock`, `event`, `depth [%]`, `t [in]`
- **Baker Hughes** (2015 format) — `Log Dist. [ft]`, `O'clock`, `Event Description`, `Depth [%]`, `Wt [in]`
- **Entegra** (2022 format) — `ILI Wheel Count [ft.]`, `O'Clock [HH:MM]`, `Metal Loss Depth [%]`, `Wt [in]`
- **Generic fallback** — Broad pattern matching for common column names
- **Fuzzy fallback** — Substring matching for unknown formats (looks for `dist`, `depth`, `clock`, `event`, etc.)

## Project Structure

```
run_pipeline.py              # CLI entry point
src/
  io.py                      # Data ingestion + auto column mapping
  preprocess.py              # Clock parsing, feature type normalisation
  alignment.py               # Piecewise linear distance alignment
  matching.py                # Segment-wise Hungarian matching
  growth.py                  # Growth rates, severity, forecasting
  clustering.py              # DBSCAN anomaly clustering
  reporting.py               # CSV/JSON output generation
  html_report.py             # HTML report with embedded charts
web_backend/
  main.py                    # FastAPI backend (auth, jobs, pipeline API)
  auth.py                    # OAuth user management + role enforcement
  users.json                 # User role store (auto-created)
web_frontend/
  auth.ts                    # NextAuth v5 config (Google + GitHub)
  middleware.ts              # Route protection middleware
  app/(app)/                 # Authenticated app pages
  app/login/                 # Login page
  components/
    TopBar.tsx               # Top navigation bar
    Sidebar.tsx              # Side navigation + user profile
    CursorGlow.tsx           # Interactive cursor light effect
    ResultsDashboard.tsx     # KPI cards + charts
    GrowthTrendChart.tsx     # Growth area chart
    RiskSegments.tsx         # Severity-ranked risk list
    MatchesTable.tsx         # Paginated matches table
    UploadForm.tsx           # Drag & drop file upload
tests/                       # pytest suite
```

## Testing

```bash
python -m pytest tests/ -v
python -m pytest tests/ --cov=src --cov-report=term-missing
```

## Troubleshooting

**"No control points could be matched"** — Ensure both runs contain girth welds, valves, or similar fixed features.

**Column mapping not detected** — The auto-detection covers Rosen, Baker Hughes, Entegra, and generic formats. For new vendors, add a mapping config in `src/io.py` → `MAPPING_CONFIGS` or rely on the fuzzy fallback.

**All anomalies MISSING/NEW** — Increase `--dist_tol` or `--clock_tol`. Large odometer drift may require wider tolerances.

**Negative growth rates** — Flagged as measurement errors. These anomalies are included in outputs with `negative_growth_flag = True` but their remaining life is set to infinity.

**OAuth errors** — Verify redirect URIs match exactly: `http://localhost:3000/api/auth/callback/google` and `http://localhost:3000/api/auth/callback/github`.

## License

See repository for license details.
