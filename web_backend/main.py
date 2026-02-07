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

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
    enable_multirun: bool = False
    run_years: Optional[str] = None  # e.g., "8,7"
    runs: Optional[str] = None       # e.g., "2007,2015,2022"
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
        except:
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
    # Assuming we run from project root, so 'python run_pipeline.py ...'
    cmd = [sys.executable, "run_pipeline.py"]
    
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
            # Maybe just validation or single file processing?
            cmd.append(str(UPLOAD_DIR / config.files[0]))
    
    # Common flags
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
    
    try:
        # Run subprocess
        log_file = job_dir / "pipeline.log"
        with open(log_file, "w") as log:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=log,
                stderr=log,
                cwd=str(Path.cwd())  # Run in project root
            )
            await process.wait()
            
        if process.returncode == 0:
            jobs_db[job_id]["status"] = "completed"
            jobs_db[job_id]["end_time"] = datetime.now().isoformat()
            
            # Move outputs to job_dir
            source_outputs = Path("outputs")
            if source_outputs.exists():
                for item in source_outputs.iterdir():
                    if item.is_file():
                        shutil.copy2(item, job_dir)
                    elif item.is_dir():
                        shutil.copytree(item, job_dir / item.name, dirs_exist_ok=True)
            
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

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload ILI data files."""
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

@app.post("/run")
async def run_job(config: PipelineConfig, background_tasks: BackgroundTasks):
    """Start a pipeline job."""
    job_id = str(uuid.uuid4())
    
    job_record = {
        "job_id": job_id,
        "status": "pending",
        "start_time": datetime.now().isoformat(),
        "config": config.dict(),
    }
    
    jobs_db[job_id] = job_record
    save_jobs()
    
    # Start background task
    background_tasks.add_task(run_pipeline_task, job_id, config)
    
    return job_record

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get job status."""
    if job_id not in jobs_db:
        raise HTTPException(404, "Job not found")
    return jobs_db[job_id]

@app.get("/jobs")
async def list_jobs():
    """List all jobs."""
    return list(jobs_db.values())

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

