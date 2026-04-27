from fastapi import FastAPI

server = FastAPI()

@server.get("/")
async def Root():
    return { "message": "Server Root" } 