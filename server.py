import os
import shutil
import uuid
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Optional

try:
    from src.parser import PDFParser
    from src.analyzer import FormAnalyzer
    from src.generator import FormGenerator
except ImportError:
    pass

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

tasks: Dict[str, Dict] = {}


class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: int
    message: str
    download_url: Optional[str] = None


def process_pdf_task(task_id: str, input_path: str, filename: str):
    output_filename = f"fillable_{filename}"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    try:
        tasks[task_id]["status"] = "processing"
        tasks[task_id]["progress"] = 10
        tasks[task_id]["message"] = "Parsing PDF..."

        pdf_parser = PDFParser(input_path)
        all_fields = []

        total_pages = len(pdf_parser.doc)

        for i, page_num in enumerate(range(total_pages)):
            tasks[task_id]["progress"] = 10 + int((i / total_pages) * 40)
            tasks[task_id][
                "message"
            ] = f"Analyzing page {page_num + 1} of {total_pages}..."

            try:
                text_elements, visual_elements = pdf_parser.parse_page(page_num)

                analyzer = FormAnalyzer(text_elements, visual_elements)
                analyzer.detect_candidates()  # runs deduplicate + filter + associate_labels internally

                fields = analyzer.get_fields()  # returns self.candidates
                all_fields.extend(fields)

                print(f"Page {page_num + 1}: {len(fields)} fields detected")

            except Exception as page_error:
                print(f"Error on page {page_num + 1}: {page_error}")
                # continue processing remaining pages
                continue

        pdf_parser.close()

        tasks[task_id]["progress"] = 60
        tasks[task_id]["message"] = "Generating fillable PDF..."

        generator = FormGenerator()
        generator.generate(input_path, output_path, all_fields)

        tasks[task_id]["progress"] = 100
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["message"] = "Done!"
        tasks[task_id]["download_url"] = f"/download/{output_filename}"

    except Exception as e:
        print(f"Error processing task {task_id}: {e}")
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["message"] = str(e)


@app.post("/upload", response_model=Dict[str, str])
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    task_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    tasks[task_id] = {
        "status": "queued",
        "progress": 0,
        "message": "Queued...",
        "download_url": None,
    }

    background_tasks.add_task(process_pdf_task, task_id, file_path, file.filename)

    return {"task_id": task_id}


@app.get("/status/{task_id}", response_model=TaskStatus)
async def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatus(
        task_id=task_id,
        status=tasks[task_id]["status"],
        progress=tasks[task_id]["progress"],
        message=tasks[task_id]["message"],
        download_url=tasks[task_id]["download_url"],
    )


@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
