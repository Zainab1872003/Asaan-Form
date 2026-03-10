from fastapi import APIRouter, UploadFile, File, Form
import shutil
import uuid
from graph.main_graph import main_graph

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
        "files": [file_path],
        "english_text": None,
        "urdu_text": None,
        "merged_json": None
    })

    return {
        "data": result.get("merged_json"),
        "english_ocr": result.get("english_text"),
        "urdu_ocr": result.get("urdu_text")
    }