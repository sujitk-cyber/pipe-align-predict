import math
import os
import shutil
import sys
import uuid
import asyncio
import subprocess
import json
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query, Depends, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from web_backend.auth import (
    get_current_user, require_role, register_user, set_user_role,
    list_users, UserInfo,
)

# Add parent directory to path to import src modules (for potential direct usage)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

app = FastAPI(
    title="WeldWarp API",
    description="Backend for ILI Pipeline Web App",
    version="0.1.0"
)

# CORS Configuration
origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BASE_DIR = Path("web_backend")
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
JOBS_FILE = BASE_DIR / "jobs.json"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Models ---

class PipelineConfig(BaseModel):
    files: List[str]  # List of filenames in uploads/
    sheet_a: Optional[str] = None  # Sheet name for Run A (for multi-sheet xlsx)
    sheet_b: Optional[str] = None  # Sheet name for Run B
    enable_multirun: bool = False
    run_years: Optional[str] = None  # e.g., "8,7"
    runs: Optional[str] = None       # e.g., "2007,2015,2022"
    years: float = 5.0               # Years between runs (for pairwise)
    clustering_epsilon: float = 5.0
    enable_confidence: bool = True
    html_report: bool = True

class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, running, completed, failed
    start_time: str
    end_time: Optional[str] = None
    output_dir: Optional[str] = None
    error: Optional[str] = None

# --- Job Management ---

# Simple in-memory + file persistence for jobs
jobs_db: Dict[str, dict] = {}

def load_jobs():
    global jobs_db
    if JOBS_FILE.exists():
        try:
            with open(JOBS_FILE, "r") as f:
                jobs_db = json.load(f)
        except (json.JSONDecodeError, IOError, OSError):
            jobs_db = {}

def save_jobs():
    with open(JOBS_FILE, "w") as f:
        json.dump(jobs_db, f, indent=2)

load_jobs()

async def run_pipeline_task(job_id: str, config: PipelineConfig):
    """
    Executes run_pipeline.py as a subprocess.
    """
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Update status to running
    jobs_db[job_id]["status"] = "running"
    save_jobs()
    
    # Construct command
    # Use the venv Python explicitly to avoid bytecode cache issues
    venv_python = Path(__file__).parent.parent / "venv" / "bin" / "python"
    cmd = [str(venv_python), "run_pipeline.py"]
    
    # Inputs: Just take the first 2 files for now logic, or --runs for multirun
    # The current CLI supports 2 files as positional args OR multirun logic.
    # We need to map config.files to CLI args.
    
    # If multirun is enabled, we expect config.files to be handled via --runs argument logic inside pipeline?
    # Actually current CLI: run_pipeline.py file1 file2 OR --enable_multirun ...
    
    # For MVP: If multirun, pass --enable_multirun and config.runs
    # If single run, pass file1 file2
    
    cli_args = []
    
    if config.enable_multirun:
        cmd.append("--enable_multirun")
        if config.runs:
            cmd.extend(["--runs", config.runs])
        if config.run_years:
            cmd.extend(["--run_years", config.run_years])
        # pass the multirun consolidated file? It usually expects one input file with multiple sheets?
        # Or individual files?
        # The CLI 'run_multirun_pipeline' takes 'file_path' and 'run_specs'.
        # We'll pass the first uploaded file as the main input.
        if config.files:
            input_path = UPLOAD_DIR / config.files[0]
            cmd.append(str(input_path))
            
    else:
        # Single Run Matching (Pairwise)
        if len(config.files) >= 2:
            file_a = UPLOAD_DIR / config.files[0]
            file_b = UPLOAD_DIR / config.files[1]
            cmd.append(str(file_a))
            cmd.append(str(file_b))
        elif len(config.files) == 1:
            # Single file with two sheets
            input_file = UPLOAD_DIR / config.files[0]
            cmd.append(str(input_file))
            
            # Auto-detect sheets if not provided
            sheet_a = config.sheet_a
            sheet_b = config.sheet_b
            if not sheet_a or not sheet_b:
                ext = input_file.suffix.lower()
                if ext in (".xlsx", ".xls", ".xlsm", ".xlsb"):
                    try:
                        xls = pd.ExcelFile(input_file)
                        data_sheets = [s for s in xls.sheet_names
                                       if s.lower() not in ("summary", "info", "metadata", "readme", "notes")]
                        if len(data_sheets) >= 2:
                            sheet_a = sheet_a or data_sheets[0]
                            sheet_b = sheet_b or data_sheets[1]
                    except Exception:
                        pass
            
            if sheet_a:
                cmd.extend(["--sheet_a", str(sheet_a)])
            if sheet_b:
                cmd.extend(["--sheet_b", str(sheet_b)])
        
        # Also pass sheets for multi-file case if provided
        if len(config.files) >= 2:
            if config.sheet_a:
                cmd.extend(["--sheet_a", str(config.sheet_a)])
            if config.sheet_b:
                cmd.extend(["--sheet_b", str(config.sheet_b)])
    
    # Auto-compute years from sheet names if they look like years and default was used
    years = config.years
    if config.sheet_a and config.sheet_b and years == 5.0:
        try:
            ya, yb = int(config.sheet_a), int(config.sheet_b)
            if 1900 < ya < 2100 and 1900 < yb < 2100:
                years = abs(yb - ya)
        except (ValueError, TypeError):
            pass
    
    # Common flags
    cmd.extend(["--years", str(years)])
    cmd.extend(["--output_dir", str(job_dir)])  # Outputs go directly to job dir
    
    if config.enable_confidence:
        cmd.append("--enable_confidence")
    if config.html_report:
        cmd.append("--html_report")
    if config.clustering_epsilon:
        cmd.extend(["--clustering_epsilon", str(config.clustering_epsilon)])
    
    # Output directory via 'cd' or moving files?
    # The pipeline writes to 'outputs/' by default.
    # We can pass --output argument if supported, or move files after.
    # Current pipeline hardcodes 'outputs/' or 'outputs_test/'.
    # We will let it run and then move content to job_dir?
    # Or run inside job_dir?
    # Running inside job_dir might break relative imports.
    # Safer: Run in project root, then move 'outputs/*' to job_dir.
    
    import logging as _logging
    _logging.info("Pipeline command: %s", " ".join(cmd))
    
    try:
        # Run subprocess with PYTHONDONTWRITEBYTECODE to avoid cached bytecode
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        
        log_file = job_dir / "pipeline.log"
        with open(log_file, "w") as log:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=log,
                stderr=log,
                cwd=str(Path.cwd()),  # Run in project root
                env=env
            )
            await process.wait()
            
        if process.returncode == 0:
            jobs_db[job_id]["status"] = "completed"
            jobs_db[job_id]["end_time"] = datetime.now().isoformat()
            # NOTE: We now pass --output_dir directly to the pipeline,
            # so no need to copy files from outputs/
            
        else:
            jobs_db[job_id]["status"] = "failed"
            jobs_db[job_id]["error"] = f"Process exited with code {process.returncode}"
            
    except Exception as e:
        jobs_db[job_id]["status"] = "failed"
        jobs_db[job_id]["error"] = str(e)
    
    jobs_db[job_id]["end_time"] = datetime.now().isoformat()
    save_jobs()


# --- Endpoints ---

@app.get("/")
def read_root():
    return {"message": "Welcome to WeldWarp API"}

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "WeldWarp API"}

# --- Auth Endpoints ---

class RegisterRequest(BaseModel):
    email: str
    name: Optional[str] = None
    image: Optional[str] = None
    provider: Optional[str] = None


@app.post("/auth/register")
async def auth_register(req: RegisterRequest):
    """Register/login a user (called by NextAuth on sign-in)."""
    user = register_user(req.email, req.name, req.image, req.provider)
    return user


@app.get("/me")
async def get_me(user: UserInfo = Depends(get_current_user)):
    """Return current user info."""
    return user


@app.get("/admin/users")
async def admin_list_users(user: UserInfo = Depends(require_role("admin"))):
    """List all users (admin only)."""
    return list_users()


class RoleUpdate(BaseModel):
    email: str
    role: str


@app.put("/admin/users/role")
async def admin_set_role(update: RoleUpdate, user: UserInfo = Depends(require_role("admin"))):
    """Update a user's role (admin only)."""
    try:
        updated = set_user_role(update.email, update.role)
        return updated
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))


# --- Pipeline Endpoints ---

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...), user: UserInfo = Depends(require_role("admin", "engineer"))):
    """Upload ILI data files (admin/engineer only)."""
    uploaded_files = []
    for file in files:
        if not file.filename: continue
        file_path = UPLOAD_DIR / file.filename
        try:
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_files.append(file.filename)
        except Exception as e:
            raise HTTPException(500, detail=str(e))
    return {"message": "Uploaded", "files": uploaded_files}


@app.get("/sheets/{filename}")
async def get_sheets(filename: str):
    """Return sheet names for an uploaded Excel file."""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    ext = file_path.suffix.lower()
    if ext not in (".xlsx", ".xls", ".xlsm", ".xlsb"):
        return {"sheets": []}
    try:
        xls = pd.ExcelFile(file_path)
        return {"sheets": xls.sheet_names}
    except Exception as e:
        raise HTTPException(400, detail=f"Cannot read sheets: {e}")

def _generate_short_id() -> str:
    """Generate a short human-friendly job ID like WLD-4A92-BX."""
    import random, string
    chars = string.ascii_uppercase + string.digits
    seg1 = "".join(random.choices(chars, k=4))
    seg2 = "".join(random.choices(chars, k=2))
    return f"WLD-{seg1}-{seg2}"


@app.post("/run")
async def run_job(config: PipelineConfig, background_tasks: BackgroundTasks, user: UserInfo = Depends(require_role("admin", "engineer"))):
    """Start a pipeline job (admin/engineer only)."""
    job_id = _generate_short_id()
    
    # Build a human label from config
    source_label = config.files[0] if config.files else "unknown"
    if config.sheet_a and config.sheet_b:
        source_label = f"{source_label} ({config.sheet_a} vs {config.sheet_b})"

    job_record = {
        "job_id": job_id,
        "status": "pending",
        "start_time": datetime.now().isoformat(),
        "source_label": source_label,
        "created_by": user.email,
        "shared_with": [],  # list of emails this job is shared with
        "config": config.dict(),
    }
    
    jobs_db[job_id] = job_record
    save_jobs()
    
    # Start background task
    background_tasks.add_task(run_pipeline_task, job_id, config)
    
    return job_record

def _user_can_access_job(user: UserInfo, job: dict) -> bool:
    """Check if a user can access a job based on role and ownership."""
    if user.role == "admin":
        return True
    if job.get("created_by") == user.email:
        return True
    if user.email in job.get("shared_with", []):
        return True
    return False


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str, user: UserInfo = Depends(get_current_user)):
    """Get job status (filtered by access)."""
    if job_id not in jobs_db:
        raise HTTPException(404, "Job not found")
    job = jobs_db[job_id]
    if not _user_can_access_job(user, job):
        raise HTTPException(403, "You don't have access to this job")
    return job


@app.get("/jobs")
async def list_jobs(user: UserInfo = Depends(get_current_user)):
    """List jobs visible to the current user."""
    return [j for j in jobs_db.values() if _user_can_access_job(user, j)]


class ShareRequest(BaseModel):
    emails: List[str]


@app.post("/jobs/{job_id}/share")
async def share_job(job_id: str, req: ShareRequest, user: UserInfo = Depends(require_role("admin", "engineer"))):
    """Share a job with other users. Admin can share any job, engineers only their own."""
    if job_id not in jobs_db:
        raise HTTPException(404, "Job not found")
    job = jobs_db[job_id]
    if user.role != "admin" and job.get("created_by") != user.email:
        raise HTTPException(403, "You can only share your own jobs")
    
    current = set(job.get("shared_with", []))
    current.update(req.emails)
    jobs_db[job_id]["shared_with"] = list(current)
    save_jobs()
    return {"shared_with": jobs_db[job_id]["shared_with"]}


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str, user: UserInfo = Depends(require_role("admin", "engineer"))):
    """Delete a job. Admin can delete any, engineers only their own."""
    if job_id not in jobs_db:
        raise HTTPException(404, "Job not found")
    job = jobs_db[job_id]
    if user.role != "admin" and job.get("created_by") != user.email:
        raise HTTPException(403, "You can only delete your own jobs")
    
    del jobs_db[job_id]
    save_jobs()
    # Clean up output directory
    job_dir = OUTPUT_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
    return {"deleted": job_id}

@app.get("/jobs/{job_id}/files/{filename}")
async def get_job_file(job_id: str, filename: str):
    """Serve a specific result file from a job's output directory."""
    if job_id not in jobs_db:
        raise HTTPException(404, "Job not found")
    
    job_dir = OUTPUT_DIR / job_id
    file_path = job_dir / filename
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(404, "File not found")
        
    return FileResponse(file_path, media_type="application/octet-stream", filename=filename)


# --- Helper to load job output files ---

def _job_dir(job_id: str) -> Path:
    if job_id not in jobs_db:
        raise HTTPException(404, "Job not found")
    d = OUTPUT_DIR / job_id
    if not d.exists():
        raise HTTPException(404, "Job output directory not found")
    return d


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise HTTPException(404, f"{path.name} not found")
    with open(path) as f:
        return json.load(f)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise HTTPException(404, f"{path.name} not found")
    return pd.read_csv(path)


def _safe_float(val, decimals: int = 4):
    """Convert to rounded float, returning None for NaN/Inf."""
    if val is None or pd.isna(val):
        return None
    f = float(val)
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, decimals)


# --- New API Endpoints ---

@app.get("/jobs/{job_id}/metrics")
async def get_job_metrics(job_id: str):
    """Structured KPI metrics parsed from alignment_report.json."""
    report = _read_json(_job_dir(job_id) / "alignment_report.json")

    matching = report.get("matching", {})
    alignment = report.get("alignment", {})
    growth = report.get("growth_summary", {})

    # Build confidence distribution from matched_results.csv if available
    confidence_distribution = {"High": 0, "Medium": 0, "Low": 0}
    csv_path = _job_dir(job_id) / "matched_results.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        if "confidence_label" in df.columns:
            counts = df["confidence_label"].value_counts().to_dict()
            for k, v in counts.items():
                confidence_distribution[str(k)] = int(v)

    return {
        "total_matches": matching.get("total_matched", 0),
        "confident_matches": matching.get("confident", 0),
        "uncertain_matches": matching.get("uncertain", 0),
        "new_anomalies": matching.get("new_run_b_only", 0),
        "missing_anomalies": matching.get("missing_run_a_only", 0),
        "avg_dist_error": alignment.get("mean_residual_ft"),
        "max_dist_error": alignment.get("max_residual_ft"),
        "confidence_distribution": confidence_distribution,
        "growth_summary": growth,
        "top_10_severity": report.get("top_10_severity", []),
    }


@app.get("/jobs/{job_id}/matches")
async def get_job_matches(
    job_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    sort_by: Optional[str] = None,
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    confidence: Optional[str] = None,
    feature_type: Optional[str] = None,
):
    """Paginated, sortable, filterable list of matched anomalies."""
    df = _read_csv(_job_dir(job_id) / "matched_results.csv")

    # Filters
    if confidence and "confidence_label" in df.columns:
        df = df[df["confidence_label"].str.lower() == confidence.lower()]
    if feature_type and "feature_type" in df.columns:
        df = df[df["feature_type"].str.lower() == feature_type.lower()]

    total = len(df)

    # Sort
    if sort_by and sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=(sort_order == "asc"), na_position="last")

    # Paginate
    pages = max(1, math.ceil(total / limit))
    start = (page - 1) * limit
    df_page = df.iloc[start : start + limit]

    # Replace NaN/Inf with None for JSON serialisation
    records = df_page.to_dict(orient="records")
    for rec in records:
        for k, v in rec.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                rec[k] = None

    return {"data": records, "total": total, "page": page, "pages": pages}


@app.get("/jobs/{job_id}/growth-trends")
async def get_growth_trends(job_id: str, bins: int = Query(50, ge=10, le=200)):
    """Growth data binned by odometer (distance_a) for charting."""
    df = _read_csv(_job_dir(job_id) / "matched_results.csv")

    if "distance_a" not in df.columns or "depth_growth_pct_per_yr" not in df.columns:
        return []

    df = df.dropna(subset=["distance_a", "depth_growth_pct_per_yr"])
    if df.empty:
        return []

    df["bin"] = pd.cut(df["distance_a"], bins=bins, labels=False)
    grouped = df.groupby("bin").agg(
        odometer=("distance_a", "mean"),
        avg_growth=("depth_growth_pct_per_yr", "mean"),
        max_growth=("depth_growth_pct_per_yr", "max"),
        avg_severity=("severity_score", "mean") if "severity_score" in df.columns else ("depth_growth_pct_per_yr", "max"),
        count=("distance_a", "size"),
    ).reset_index(drop=True)

    # Round for cleaner JSON
    for col in ["odometer", "avg_growth", "max_growth", "avg_severity"]:
        if col in grouped.columns:
            grouped[col] = grouped[col].round(4)

    records = grouped.to_dict(orient="records")
    for rec in records:
        for k, v in rec.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                rec[k] = None
    return records


@app.get("/jobs/{job_id}/risk-segments")
async def get_risk_segments(job_id: str, top_n: int = Query(20, ge=1, le=100)):
    """Top critical risk segments from the dig list."""
    dig_path = _job_dir(job_id) / "dig_list.csv"
    df = _read_csv(dig_path).head(top_n)

    def _risk_status(score):
        if pd.isna(score):
            return "UNKNOWN"
        if score >= 70:
            return "HIGH RISK"
        if score >= 40:
            return "MEDIUM RISK"
        return "LOW RISK"

    def _safe_str(val):
        if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
            return None
        return str(val)

    results = []
    for _, row in df.iterrows():
        results.append({
            "rank": int(row.get("rank", 0)),
            "feature_id": _safe_str(row.get("feature_id_a")),
            "feature_type": _safe_str(row.get("feature_type")),
            "odometer": _safe_float(row.get("distance_a"), 2),
            "growth_rate": _safe_float(row.get("depth_growth_pct_per_yr"), 4),
            "depth": _safe_float(row.get("depth_pct_b"), 2),
            "remaining_life": _safe_float(row.get("remaining_life_yr"), 2),
            "severity_score": _safe_float(row.get("severity_score"), 2),
            "status": _risk_status(row.get("severity_score")),
        })

    return results


@app.get("/jobs/{job_id}/feature-types")
async def get_feature_types(job_id: str):
    """Return distinct feature types from matched results."""
    csv_path = _job_dir(job_id) / "matched_results.csv"
    if not csv_path.exists():
        return []
    df = pd.read_csv(csv_path)
    if "feature_type" not in df.columns:
        return []
    types = sorted(df["feature_type"].dropna().unique().tolist())
    return types


@app.get("/jobs/{job_id}/downloads")
async def list_job_downloads(job_id: str):
    """List available output files for download."""
    job_dir = _job_dir(job_id)
    files = []
    for f in sorted(job_dir.iterdir()):
        if f.is_file():
            files.append({"filename": f.name, "size_bytes": f.stat().st_size})
    return files

