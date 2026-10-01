from fastapi import APIRouter, Depends, UploadFile, File, Form, Header
from sqlalchemy.orm import Session
from backend.db.session import get_db

router = APIRouter()

@router.post("/")
def upload_evidence(
    case_id: str = Form(...),
    file: UploadFile = File(...),
    idempotency_key: str = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    # In production, save file to S3/Blob storage and return the URL
    return {
        "id": "EVI-MOCK-1",
        "case_id": case_id,
        "file_url": f"https://mock-storage.civicconnect.com/{file.filename}",
        "media_type": file.content_type
    }
