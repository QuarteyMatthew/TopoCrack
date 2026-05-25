import logging
import time
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException

from Schemas.AnalysisSchemas import AnalysisRequest, AnalysisResponse, Point, GeographicCoords 
from Services.ImageService import ImageService
from Services.DtwService import DtwService

logger = logging.getLogger(__name__)

Router = APIRouter()

@Router.post("/analyze", response_model=AnalysisResponse)
def Analyze(request: Request, image: UploadFile = File(...), startX: int = Form(...), startY: int = Form(...), endX: int = Form(...), endY: int = Form(...)):
    startTime = time.perf_counter()

    # ---------------- 1. Costruzione della request ----------------
    try:
        imageBytes = image.file.read()
        analysisReq = AnalysisRequest(
            ImageBytes = imageBytes,
            UserStart = Point(X=startX, Y=startY),
            UserEnd = Point(X=endX, Y=endY),
        )
        
    except ValueError as e:
        logger.warning("Request validation failed: %s", e)
        raise HTTPException(status_code=422, detail=str(e))
    
    # ---------------- 2. Estrazione dei punti della crepa ----------------
    try:
        crackPoints = ImageService.ExtractCrackPoints(
            imageBytes = analysisReq.ImageBytes,
            userStart  = analysisReq.UserStart,
            userEnd    = analysisReq.UserEnd,
        )
        
    except ValueError as e:
        logger.warning("Failed to extract crack points: %s", e)
        raise HTTPException(status_code=422, detail=str(e))
    
    except Exception as e:
        logger.error("Unexpected error in ImageService: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during image processing.")
    
    # ---------------- 3. DTW e best match ----------------
    try:
        coastalData = request.app.state.CoastalData
        bestMatch, curvatureRatio = DtwService.FindBestMatch(crackPoints, coastalData)

    except Exception as e:
        logger.error("Unexpected error in DtwService: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during DTW computation.")
    
    warningMessage = None
    if curvatureRatio > DtwService.CurvatureRatioThreshold:
        warningMessage = (
            "La crepa selezionata traccia quello che sembra essere un contorno, "
            "piuttosto che una linea perlopiù dritta. "
            "I risultati potrebbero non essere ottimali."
        )

    # ---------- 4. Costruzione e restituzione della risposta ----------
    startCoord = bestMatch["startCoord"]
    endCoord = bestMatch["endCoord"]
    
    response = AnalysisResponse(
        StartCoord = GeographicCoords(Lon=startCoord[0], Lat=startCoord[1]),
        EndCoord   = GeographicCoords(Lon=endCoord[0], Lat=endCoord[1]),
        DtwScore   = bestMatch["cost"],
        StatusCode = 200,
        Message    = "Analisi completata con successo",
        Warning    = warningMessage,  # None se la crepa è lineare
    )

    elapsedTime = time.perf_counter() - startTime
    logger.info("Crack's analysis took %.6f", elapsedTime)

    return response
    