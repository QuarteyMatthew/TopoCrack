from fastapi import APIRouter

from Schemas import CrackRequest, CrackResponse
from Controller import Freature

router = APIRouter()

@router.post("/analyze", response_model=CrackResponse)
def Analyze(request: CrackRequest):
    return