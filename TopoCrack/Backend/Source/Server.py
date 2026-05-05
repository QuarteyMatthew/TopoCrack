from contextlib import asynccontextmanager
from fastapi import FastAPI

from Routes.AnalysisRoutes import Router as AnalysisRouter
from Services.CoastlineService import CoastlineService

@asynccontextmanager
async def Lifespan(server: FastAPI):
    # Avvio: carica (o rigenera) i dati della coste normalizzate.
    # Questo blocca il server finché non è prondo a gestire le richieste.
    server.state.CoastalData = CoastlineService.LoadOrBuild()
    
    # Yield è una parola chiave utilizzata per creare funzioni generatore. 
    # A differenza di return, che termina una funzione restituendo un valore, 
    # yield restituisce un valore e sospende temporaneamente l'esecuzione della funzione, 
    # salvandone lo stato locale per riprenderla esattamente da dove si era interrotta alla chiamata successiva
    yield

server = FastAPI(title="TopoCrack Backend", Lifespan=Lifespan)
server.include_router(AnalysisRouter, prefix="/api")