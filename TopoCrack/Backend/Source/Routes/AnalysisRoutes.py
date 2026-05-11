import logging
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException

from Schemas.AnalysisSchemas import AnalysisRequest, AnalysisResponse, Point, GeographicCoords 
from Services.ImageService import ImageService
from Services.DtwService import DtwService

logger = logging.getLogger(__name__)

Router = APIRouter()

@Router.post("/analyze", response_model=AnalysisResponse)
def Analyze(request: Request, image: UploadFile = File(...), startX: int = Form(...), startY: int = Form(...), endX: int = Form(...), endY: int = Form(...)):
    # ---------------- 1. Costruzione della request ----------------
    logger.info(
        "POST /analyze received: image='%s' (content-type=%s), "
        "start=(%d,%d), end=(%d,%d).",
        image.filename, image.content_type, startX, startY, endX, endY
    )
    
    try:
        imageBytes = image.file.read()
        analysisReq = AnalysisRequest(
            ImageBytes = imageBytes,
            UserStart = Point(X=startX, Y=startY),
            UserEnd = Point(X=endX, Y=endY),
        )
        
        logger.debug("AnalysisRequest built successfully: image size=%d bytes.", len(imageBytes))
        
    except ValueError as e:
        logger.warning("Request validation failed: %s", e)
        raise HTTPException(status_code=422, detail=str(e))
    
    # ---------------- 2. Estrazione dei punti della crepa ----------------
    print("============================= Stage 1: image processing =============================")
    logger.info("Invoking ImageService.ExtractCrackPoints...")
    
    coastalData = request.app.state.CoastalData
    
    try:
        crackPoints = ImageService.ExtractCrackPoints(
            imageBytes = analysisReq.ImageBytes,
            userStart  = analysisReq.UserStart,
            userEnd    = analysisReq.UserEnd,
        )
        logger.info("ImageService returned %d crack points.", len(crackPoints))
        
    except ValueError as e:
        logger.warning("ImageService failed: %s", e)
        raise HTTPException(status_code=422, detail=str(e))
    
    except Exception as e:
        logger.error("Unexpected error in ImageService: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during image processing.")
    
    # ---------------- 3. DTW e best match ----------------
    logger.info("============================= Stage 2: DTW end finding the best match =============================")
    logger.info("Invoking DtwService.FindBestMatch...")
    
    try:
        coastalData = request.app.state.CoastalData
        bestMatch = DtwService.FindBestMatch(crackPoints, coastalData)
        logger.info(
            "DtwService returned best match: featureIndex=%s, sectionIndex=%s, cost=%.6f.",
            bestMatch["featureIndex"], bestMatch["sectionIndex"], bestMatch["cost"]
        )

    except Exception as e:
        logger.error("Unexpected error in DtwService: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error during DTW computation.")
    
    # ---------- 4. Costruzione e restituzione della risposta ----------
    startCoord = bestMatch["startCoord"]
    endCoord = bestMatch["endCoord"]
    
    response = AnalysisResponse(
        StartCoord = GeographicCoords(Lon=startCoord[0], Lat=startCoord[1]),
        EndCoord   = GeographicCoords(Lon=endCoord[0], Lat=endCoord[1]),
        DtwScore   = bestMatch["cost"],
        StatusCode = 200,
        Message = "Analysis successfully completed",
    )
    
    logger.info(
        "Response ready: StartCoord=(%.4f, %.4f), EndCoord=(%.4f, %.4f), DtwScore=%.6f.",
        startCoord[0], startCoord[1], endCoord[0], endCoord[1], bestMatch["cost"]
    )
    
    return response
    