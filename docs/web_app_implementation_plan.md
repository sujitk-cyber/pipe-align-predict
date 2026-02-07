# WeldWarp Web Application Implementation Plan

## Overview
This document outlines the implementation requirements for the WeldWarp web application based on the provided Figma designs. The application serves as a modern frontend for the existing Python-based ILI matching pipeline.

## 1. Backend API Requirements (Python / FastAPI)

The backend must serve as an orchestration layer for `run_pipeline.py` and expose results via RESTful endpoints.

### 1.1 Core Endpoints

#### **Job Management**
*   `POST /api/v1/jobs`
    *   **Description**: Create a new analysis job (e.g., `WLD-4492-AX`).
    *   **Response**: `{ job_id: "uuid", status: "created" }`
*   `GET /api/v1/jobs/{job_id}/status`
    *   **Description**: Check pipeline execution status.
    *   **Response**: `{ status: "processing" | "completed" | "failed", progress: 45 }`

#### **Upload & Configuration (Design 1)**
*   `POST /api/v1/jobs/{job_id}/upload`
    *   **Description**: Handle multi-part file uploads for `run_a.csv`, `run_b.csv`, and `config.json`.
    *   **Validation**: Perform schema validation against `MAPPING_CONFIGS` (e.g., check `dist_delta`, `clock_delta`).
    *   **Response**: `{ valid: boolean, missing_columns: ["clock_delta"], validation_messages: [...] }`

#### **Results & Metrics (Design 2 & 4)**
*   `GET /api/v1/jobs/{job_id}/metrics`
    *   **Description**: Serve high-level KPIs.
    *   **Response**:
        ```json
        {
          "total_matches": 1150,
          "new_anomalies": 135,
          "missing_anomalies": 100,
          "avg_dist_error": 0.12,
          "confidence_distribution": { "high": 200, "medium": 500, "low": 450 }
        }
        ```
    *   **Source**: Parsed from `alignment_report.json` and `matched_results.csv` summary stats.

#### **Matching Review (Design 3)**
*   `GET /api/v1/jobs/{job_id}/matches`
    *   **Description**: Paginated list of matched anomalies.
    *   **Parameters**: `page`, `limit`, `sort_by`, `run_id_filter`.
    *   **Response**:
        ```json
        {
          "data": [
            {
              "match_id": "MATCH-0",
              "run_a_id": "R1-U-100",
              "run_b_id": "R2-V-200",
              "dist_diff_m": 0.271,
              "clock_diff_deg": 2.9,
              "type": "External Metal Loss",
              "confidence": "HIGH",
              "action_url": "/api/v1/jobs/{job_id}/matches/MATCH-0"
            }
          ],
          "total": 1150
        }
        ```
    *   **Source**: `matched_results.csv`.

#### **Growth & Risk (Design 5)**
*   `GET /api/v1/jobs/{job_id}/growth-trends`
    *   **Description**: Data series for "Growth Trends by Odometer" chart.
    *   **Response**: `[{ odometer: 100, growth: 2.1, risk: 1.5 }, ...]`
    *   **Source**: `tracks_multi_run.csv` (aggregated by odometer segments).
*   `GET /api/v1/jobs/{job_id}/risk-segments`
    *   **Description**: Top critical risk segments.
    *   **Response**:
        ```json
        [
          { "odometer": 1240.5, "growth_rate": "4.2mm/yr", "status": "HIGH RISK" },
          { "odometer": 2280.1, "growth_rate": "2.8mm/yr", "status": "MEDIUM RISK" }
        ]
        ```
    *   **Source**: `dig_list` logic in `src/reporting.py`.

---

## 2. Frontend Implementation (React / Next.js)

The frontend requires a component-based architecture (e.g., Shadcn UI + Tailwind CSS) to match the Figma designs.

### 2.1 Key Components

#### **Upload & Configure**
*   **FileUploader**: Drag-and-drop zone handling CSV validation feedback.
*   **SchemaValidator**: Visual indicators (Green "OK", Red "REQUIRED") dynamically updated based on uploaded file headers.
*   **PipelineTrigger**: Button to `POST /run-analysis` with loading state.

#### **Dashboard (Results)**
*   **KPICard**: Reusable card component for "Total Matches", "New Anomalies", etc.
*   **Charts**:
    *   **Confidence Distribution**: Bar chart (Recharts/Plotly).
    *   **Total Anomaly Count**: Donut chart.
*   **ArtifactLinks**: Download buttons for JSON/CSV reports.

#### **Matching Table**
*   **DataTable**: 
    *   Sortable columns (Dist Diff, Clock Diff).
    *   Filtering (by Confidence Level, Type).
    *   Pagination (Server-side via API).
    *   "View" Action: Modal or side-panel showing detailed match attributes.

#### **Growth Analytics**
*   **TrendChart**: Line chart with multi-axis support (Growth vs Risk).
*   **RiskList**: Card-based list for "Critical Risk Segments" with badge indicators (Red/Yellow/Green).

### 2.2 Integration Points

1.  **State Management**: React Query (TanStack Query) for fetching API data and handling caching/loading states.
2.  **Navigation**: Sidebar navigation explicitly matching Figma:
    *   Core Pipeline: Upload, Job Results, Matching Review.
    *   Analysis: Alignment QA (Placeholder), Growth & Risk, Exports.
    *   System: Job History, Settings.

---

## 3. Data Mapping Strategy

| Figma Field | Backend Source | CSV Column / Attribute |
| :--- | :--- | :--- |
| **Match ID** | Generated | Index or `match_id` |
| **Run 1 ID (u_id)** | `matched_results.csv` | `RunA_ID` / `feature_id_A` |
| **Run 2 ID (v_id)** | `matched_results.csv` | `RunB_ID` / `feature_id_B` |
| **Dist Diff (m)** | `matched_results.csv` | `dist_delta_ft` (convert to m) |
| **Clock Diff (°)** | `matched_results.csv` | `clock_delta_deg` |
| **Type** | `matched_results.csv` | `feature_type` (e.g., Metal Loss) |
| **Confidence** | `matched_results.csv` | `confidence_label` (High/Med/Low) |
| **Growth Rate** | `matched_results.csv` | `depth_growth_pct_per_year` |
| **Risk Status** | Derived Logic | Based on `severity_score` or `time_to_critical` |

## 4. Immediate Next Steps

1.  **Backend Setup**: Initialize FastAPI project structure (or Python Flask).
2.  **API Wrapper**: Implement `POST /upload` and `POST /run` to wrap the existing CLI execution.
3.  **Frontend Scaffold**: Create Next.js app with Tailwind and Shadcn UI components.
4.  **Connect**: Wire up the "Upload" page first to validate the end-to-end flow.
