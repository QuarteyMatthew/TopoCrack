from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException

from Schemas.AnalysisSchemas import AnalysisRequest, Point, AnalysisResponse
from Services.ImageService import ImageService
from Services.DtwService import DtwService

Router = APIRouter()

@Router.post("/analyze", response_model=AnalysisResponse)
def Analyze(request: Request, image: UploadFile = File(...), startX: int = Form(...), startY: int = Form(...), endX: int = Form(...), endY: int = Form(...)):
    try:
        analysisReq = AnalysisRequest(
            ImageBytes = image.file().read(),
            UserStart = Point(X=startX, Y=startY),
            UserEnd = Point(X=endX, Y=endY),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    coastalData = request.app.state.CoastalData
    
    crackPoints = ImageService.ExtractCrackPoints(
        ImageBytes = analysisReq.ImageBytes,
        UserStart = analysisReq.UserStart,
        UserEnd = analysisReq.UserEnd,
    )
    
    bestMatch = DtwService.FindBestMatch(crackPoints, coastalData)
    
    return AnalysisResponse(
        StartCoord = bestMatch["startCoord"],
        EndCoord   = bestMatch["endCoord"],
        DtwScore   = bestMatch["cost"],
        StatusCode = 200,
        Message = "Analysis successfully completed",
    )
    