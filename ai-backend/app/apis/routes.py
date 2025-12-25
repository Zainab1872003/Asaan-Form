from fastapi import APIRouter, UploadFile, File, Form
import shutil
import uuid
from app.graph.main_graph import main_graph

router = APIRouter()

def save_file(file: UploadFile) -> str:
    path = f"uploads/{uuid.uuid4()}_{file.filename}"
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return path

@router.post("/document/intake")
async def document_intake(
    user_input: str = Form(...),
    file: UploadFile = File(...)
):
    file_path = save_file(file)

    result = main_graph.invoke({
        "user_input": user_input,
        "files": [file_path]
    })

    return result
