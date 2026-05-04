from fastapi import UploadFile
from pydantic import BaseModel

# ========== Crack's Schemas ==========
class CrackRequest(BaseModel):
    Image: UploadFile

class CrackResponse(BaseModel):
    StausCode: int
    Message: str