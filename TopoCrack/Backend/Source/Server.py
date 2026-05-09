import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from Routes.AnalysisRoutes import Router as AnalysisRouter
from Services.CoastlineService import CoastlineService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

@asynccontextmanager
async def Lifespan(server: FastAPI):
    # ----------------- 1. Startup -----------------
    # Il lifespan è il punto di ingresso dell'intera applicazione.
    # Avvio: carica (o rigenera) i dati della coste normalizzate.
    # Questo blocca il server finché non è prondo a gestire le richieste.
    logger.info("TopoCrack Backend starting up...")
    logger.info("Loading or building coastal data: this may take several minutes on first run.")
    
    try:
        server.state.CoastalData = CoastlineService.LoadOrBuild()
        logger.info("Coastal data ready: %d sections loaded into server state.", len(server.state.CoastalData))
        
    except Exception as e:
        # Se il caricamento fallisce il server non può gestire nessuna
        # richiesta: loga come CRITICAL ed inca 'raise' per bloccare l'avvio.
        logger.critical("Failed to load coastal data during startup: %s. " "The server cannot start without this data.", e, exc_info=True)
        raise

    logger.info("Server ready to accept requests.")

    # Yield è una parola chiave utilizzata per creare funzioni generatore. 
    # A differenza di return, che termina una funzione restituendo un valore, 
    # yield restituisce un valore e sospende temporaneamente l'esecuzione della funzione, 
    # salvandone lo stato locale per riprenderla esattamente da dove si era interrotta alla chiamata successiva
    yield
    
    # ----------------- 2. Shutdown -----------------
    logger.info("TopoCrack Backend shutting down...")
    
server = FastAPI(title="TopoCrack Backend", lifespan=Lifespan)
server.include_router(AnalysisRouter, prefix="/api")