from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Routes import Crack
from Routes import Analyzer

server = FastAPI(
    title="TopoCrack Backend",
    verion="0.1.0",
    description="TopoCrack's backend server"
)

server.middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

server.include_router(Crack.router, prefix="/api/crack", tags=["crack"])