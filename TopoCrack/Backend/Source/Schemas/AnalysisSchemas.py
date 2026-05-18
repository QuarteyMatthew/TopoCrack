from pydantic import BaseModel, field_validator
import numpy as np

class Point(BaseModel):
    X: int
    Y: int
    
    def ToTuple(self) -> tuple[int, int]:
        return (self.X, self.Y)

class GeographicCoords(BaseModel):
    # Coordinate WGS84 (lon, lat)
    Lon: float
    Lat: float
    
    def ToTuple(self) -> tuple[float, float]:
        return (self.Lon, self.Lat)

class AnalysisRequest(BaseModel):
    ImageBytes: bytes
    UserStart : Point
    UserEnd   : Point
    
    model_config = {"arbitrary_types_allowed": True}
    
    @field_validator("ImageBytes")
    @classmethod
    def ImageMustNotBeEmpty(cls, Value: bytes) -> bytes:
        if not Value:
            raise ValueError("The uploaded image is blank")
        
        return Value

class AnalysisResponse(BaseModel):
    StartCoord: GeographicCoords
    EndCoord  : GeographicCoords
    DtwScore  : float
    
    StatusCode: int
    Message   : str
    Warning   : str | None = None