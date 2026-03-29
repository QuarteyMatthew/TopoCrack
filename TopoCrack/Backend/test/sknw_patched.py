import numpy as np
import networkx as nx

# -----------------------------------------------------------------------------
# sknw_patched.py - 2D skeleton-to-graph (pure Python + NumPy)
# -----------------------------------------------------------------------------
# Version: commented, no Numba
#
# Scopo:
#   - Prende uno skeleton binario 2D (array dtype uint8 o simile, valori 0/1)
#   - Aggiunge padding per evitare controlli di bounds
#   - Marca i pixel della skeleton in due tipi:
#       1 -> pixel di passaggio (degree == 2)
#       2 -> pixel nodo (degree != 2)
#   - Raggruppa i pixel di tipo 2 in "nodi" (componenti connessi)
#   - Traccia gli "archi" partendo dai pixel di tipo 1 fino a raggiungere nodi
#   - Costruisce un grafo NetworkX con nodi (coordinate) e archi (lista di punti)
#
# Motivazione:
#   - Versione senza JIT/Numba per compatibilità con Python/NumPy moderni.
#   - Mantiene la logica originale del progetto sknw ma con codice più leggibile.
#
# Nota sulle prestazioni:
#   - Per immagini moderate (es. 600x400) questo approccio è sufficientemente veloce.
#   - Se serve più velocità, si possono ottimizzare parti critiche con Cython o Numba
#     su funzioni isolate (non sull'intero flusso).
# -----------------------------------------------------------------------------

# ---------- Helpers for 2D ---------------------------------------------------

def neighbors(shape):
    """
    Restituisce gli offset lineari per la 8-neighborhood in una immagine 2D.

    Parametri
    - shape: tuple (rows, cols) della matrice (es. (h, w))

    Ritorno
    - array 1D dtype int64 con 8 offset lineari da sommare a un indice ravelato.
      L'ordine è:
        (-1,-1), (-1,0), (-1,1),
        ( 0,-1),         ( 0,1),
        ( 1,-1), ( 1,0), ( 1,1)
    Spiegazione:
    - Per un'immagine row-major (C order), indice lineare = r * width + c.
    - Quindi l'offset lineare di (dr, dc) è dr*width + dc.
    """
    h, w = shape
    # dr e dc sono gli spostamenti di riga e colonna per i 8 vicini
    dr = np.array([-1, -1, -1, 0, 0, 1, 1, 1], dtype=np.int64)
    dc = np.array([-1,  0,  1, -1, 1, -1, 0, 1], dtype=np.int64)
    # convertiamo in offset lineari
    return (dr * w + dc).astype(np.int64)


def idx2rc(idx, acc):
    """
    Converte indici lineari in coordinate (r, c) rispetto a un array ravelato.

    Parametri
    - idx: array 1D di indici lineari (int64)
    - acc: array di fattori di divisione (per 2D acc = [width, 1])

    Ritorno
    - array shape (N, 2) dtype int16 con coordinate (r, c) per ogni indice.
    Note:
    - La funzione sottrae 1 alla fine per compensare il padding usato nel codice
      originale (il codice originale usa coordinate con offset -1).
    - Usata per ottenere le coordinate reali dei punti di un nodo o di un arco.
    """
    idx = idx.copy().astype(np.int64)
    rst = np.zeros((len(idx), len(acc)), dtype=np.int16)
    for i in range(len(idx)):
        for j in range(len(acc)):
            rst[i, j] = idx[i] // acc[j]
            idx[i] -= int(rst[i, j]) * acc[j]
    rst -= 1  # compensazione per il padding (coerenza con implementazione originale)
    return rst


# ---------- Core algorithms (Python + NumPy) --------------------------------

def mark(img):
    """
    Marca l'immagine ravelata (con padding) in due tipi:
      - 1: pixel di passaggio (degree == 2)
      - 2: pixel nodo (degree != 2)

    Comportamento:
    - img è un array NumPy (es. uint16) con padding di 1 pixel attorno allo skeleton.
    - La funzione lavora su img.ravel() e modifica i valori in-place.
    - Si assume che i pixel di skeleton iniziali siano != 0 (tipicamente 1).
    - I pixel di background sono 0 e vengono ignorati.
    - Per ogni pixel non-zero si conta quanti vicini non-zero ha (8-neighborhood).
      - se count == 2 -> setta 1 (passaggio)
      - altrimenti -> setta 2 (nodo)
    Note implementative:
    - L'uso del padding evita controlli di bounds quando si accede a p+dp.
    - La funzione è volutamente semplice e imperativa per chiarezza.
    """
    nbs = neighbors(img.shape)
    flat = img.ravel()
    L = len(flat)
    for p in range(L):
        if flat[p] == 0:
            continue
        s = 0
        # somma i vicini non-zero
        for dp in nbs:
            if flat[p + int(dp)] != 0:
                s += 1
        # degree 2 => passaggio, altrimenti nodo
        flat[p] = 1 if s == 2 else 2


def fill(img, p, num, nbs, acc, buf):
    """
    Riempie un componente con etichetta 'num' partendo dall'indice lineare p.

    Parametri
    - img: array ravelato (modificato in-place)
    - p: indice lineare di partenza (int)
    - num: valore numerico da assegnare al componente (es. 10, 11, ...)
    - nbs: array di offset lineari per i vicini (8 elementi)
    - acc: array per conversione indici->(r,c)
    - buf: buffer (non strettamente necessario in questa versione Python)

    Ritorno
    - array (N,2) con coordinate (r,c) dei punti del componente (nodo)
    Comportamento:
    - Esegue una BFS/riempimento flood-fill su tutti i pixel con valore 'back'
      (valore originale del pixel p) e li etichetta con 'num'.
    - Restituisce le coordinate convertite con idx2rc.
    """
    back = img[p]
    img[p] = num
    buf_list = [p]  # lista dinamica dei punti del componente
    cur = 0
    while cur < len(buf_list):
        pcur = buf_list[cur]
        for dp in nbs:
            cp = int(pcur + dp)
            if img[cp] == back:
                img[cp] = num
                buf_list.append(cp)
        cur += 1
    buf_arr = np.array(buf_list, dtype=np.int64)
    return idx2rc(buf_arr, acc)


def trace(img, p, nbs, acc, buf):
    """
    Traccia un arco a partire da un pixel di tipo 1 (passaggio).

    Parametri
    - img: array ravelato (modificato in-place)
    - p: indice lineare del pixel di partenza (int)
    - nbs: offset dei vicini
    - acc: array per idx2rc
    - buf: buffer (non strettamente necessario qui)

    Ritorno
    - tuple (start_node_index, end_node_index, pts_array)
      dove pts_array è un array (M,2) con le coordinate dei pixel dell'arco.

    Logica:
    - Scorre i pixel di tipo 1 consumandoli (li imposta a 0) per evitare doppie visite.
    - Se incontra pixel con valore >= 10 significa che ha raggiunto un nodo
      (i nodi sono stati etichettati con valori 10,11,... da fill).
    - La funzione termina quando trova due nodi (c1 e c2) o non trova più
      pixel di tipo 1 da seguire.
    """
    c1 = 0
    c2 = 0
    pcur = p
    buf_list = []
    while True:
        buf_list.append(pcur)
        img[pcur] = 0  # consumiamo il pixel dell'arco per non riesaminarlo
        found_newp = 0
        for dp in nbs:
            cp = int(pcur + dp)
            val = img[cp]
            if val >= 10:
                if c1 == 0:
                    c1 = int(val)
                else:
                    c2 = int(val)
            if val == 1:
                found_newp = cp
        if found_newp != 0:
            pcur = found_newp
        else:
            # non abbiamo trovato un successivo pixel di tipo 1
            break
        if c2 != 0:
            # abbiamo trovato il secondo nodo: arco completo
            break
    pts = np.array(buf_list, dtype=np.int64)
    
    if c1 == 0 or c2 == 0:
        return None  # arco invalido
    return (int(c1 - 10), int(c2 - 10), idx2rc(pts, acc))


def parse_struc(img):
    """
    Analizza l'immagine marcata (con padding) e restituisce nodes e edges.

    Flusso:
    1. Calcola acc per conversione indici->(r,c).
    2. Trova tutti gli indici con valore 2 (nodi non ancora raggruppati).
    3. Per ogni indice p con valore 2, chiama fill() per ottenere le coordinate
       del nodo e lo etichetta con num (10,11,...).
    4. Cerca tutti i pixel di tipo 1 (archi) e per ciascuno chiama trace()
       per ottenere (start_node, end_node, pts).
    5. Restituisce nodes (lista di array Nx2) e edges (lista di tuple).

    Nota:
    - Usiamo un buffer di dimensione fissa per compatibilità con l'algoritmo
      originale; in questa versione Python non è strettamente necessario ma
      lo manteniamo per chiarezza.
    """
    nbs = neighbors(img.shape)

    # acc: fattori per convertire coordinate in indice lineare su ravel
    # per 2D: acc = [width, 1]
    shape_vec = np.array((1,) + img.shape[::-1][:-1], dtype=np.int64)
    acc = np.cumprod(shape_vec)[::-1]

    flat = img.ravel()
    # trova tutti gli indici con valore 2 (nodi)
    pts = np.where(flat == 2)[0]

    buf = np.zeros(131072, dtype=np.int64)  # buffer legacy
    num = 10  # valore iniziale per etichettare i nodi (10, 11, ...)
    nodes = []
    for p in pts:
        if flat[p] == 2:
            nds = fill(flat, int(p), num, nbs, acc, buf)
            num += 1
            nodes.append(nds)

    edges = []
    # dopo aver etichettato i nodi, cerchiamo gli archi: pixel con valore 1
    arc_pts = np.where(flat == 1)[0]
    for p in arc_pts:
        # se troviamo un vicino che è un nodo (>=10), tracciamo l'arco
        # trace() consumerà i pixel dell'arco (li imposterà a 0)
        for dp in nbs:
            if flat[int(p + dp)] >= 10:
                edge = trace(flat, int(p), nbs, acc, buf)
                edges.append(edge)
                break
    return nodes, edges


# ---------- Graph building and utilities ------------------------------------

def build_graph(nodes, edges, multi=False):
    """
    Costruisce un grafo NetworkX a partire da nodes e edges.

    Parametri
    - nodes: lista di array (Ni, 2) con coordinate dei punti di ciascun nodo
    - edges: lista di tuple (s, e, pts_array) dove s,e sono indici di nodo
    - multi: se True costruisce un MultiGraph, altrimenti Graph

    Per ogni nodo:
    - aggiunge attributi:
        - pts: array (Ni,2) dei punti del nodo
        - o: centroide (mean) dei punti (coordinate float)

    Per ogni arco:
    - calcola la lunghezza l come somma delle distanze euclidee tra punti
      consecutivi dell'arco (approssimazione della lunghezza)
    - aggiunge l'arco con attributi pts e weight
    """
    graph = nx.MultiGraph() if multi else nx.Graph()
    for i, nd in enumerate(nodes):
        pts = np.array(nd, dtype=np.int64)
        graph.add_node(i, pts=pts, o=pts.mean(axis=0))
        
    edges = [e for e in edges if e!=None] # Removes None edges
    for s, e, pts in edges:
        pts = np.array(pts, dtype=np.int64)
        if pts.shape[0] > 1:
            l = np.linalg.norm(pts[1:] - pts[:-1], axis=1).sum()
        else:
            l = 0.0
        graph.add_edge(int(s), int(e), pts=pts, weight=float(l))
    return graph


def buffer(ske):
    """
    Aggiunge padding di 1 pixel intorno allo skeleton per evitare controlli di bounds.

    Parametri
    - ske: array 2D binario (0/1)

    Ritorno
    - buf: array 2D con shape (h+2, w+2) dtype uint16, con ske inserito al centro.
    """
    pad_shape = tuple(np.array(ske.shape) + 2)
    buf = np.zeros(pad_shape, dtype=np.uint16)
    slices = tuple([slice(1, -1)] * buf.ndim)
    buf[slices] = ske
    return buf


def build_sknw(ske, multi=False):
    """
    Interfaccia principale: prende uno skeleton binario (0/1) e costruisce il grafo.

    Flusso:
    - crea buffer con padding
    - marca i pixel (mark)
    - estrae nodes e edges (parse_struc)
    - costruisce e ritorna il grafo NetworkX
    """
    buf = buffer(ske)
    mark(buf)  # modifica buf in-place: setta 1/2 sui pixel della skeleton
    nodes, edges = parse_struc(buf)
    return build_graph(nodes, edges, multi)


def draw_graph(img, graph, cn=255, ce=128):
    """
    Disegna nodi e archi su immagine 2D (grayscale).
    Supporta networkx.Graph e networkx.MultiGraph.
    """
    if img.ndim != 2:
        raise ValueError("draw_graph: img deve essere 2D (grayscale).")

    h, w = img.shape
    flat = img.ravel()
    # fattori per (row, col) -> indice lineare
    # (row * w + col)
    # acc non usato con dot per maggiore chiarezza: calcoliamo inds direttamente
    # acc = np.array((w, 1), dtype=np.int64)

    # --- disegna nodi ---
    for n, data in graph.nodes(data=True):
        pts = data.get('pts') if isinstance(data, dict) else None
        if pts is None:
            continue
        pts = np.asarray(pts, dtype=np.int64)
        if pts.size == 0:
            continue
        rows = np.clip(pts[:, 0], 0, h - 1).astype(np.intp)
        cols = np.clip(pts[:, 1], 0, w - 1).astype(np.intp)
        inds = rows * w + cols
        flat[inds] = cn

    # --- disegna archi: gestisce Graph e MultiGraph ---
    if isinstance(graph, nx.MultiGraph):
        # MultiGraph: edges(keys=True, data=True) -> (u, v, key, data)
        for u, v, key, data in graph.edges(keys=True, data=True):
            pts = data.get('pts') if isinstance(data, dict) else None
            if pts is None:
                continue
            pts = np.asarray(pts, dtype=np.int64)
            if pts.size == 0:
                continue
            rows = np.clip(pts[:, 0], 0, h - 1).astype(np.intp)
            cols = np.clip(pts[:, 1], 0, w - 1).astype(np.intp)
            inds = rows * w + cols
            flat[inds] = ce
    else:
        # Graph: edges(data=True) -> (u, v, data)
        for u, v, data in graph.edges(data=True):
            pts = data.get('pts') if isinstance(data, dict) else None
            if pts is None:
                continue
            pts = np.asarray(pts, dtype=np.int64)
            if pts.size == 0:
                continue
            rows = np.clip(pts[:, 0], 0, h - 1).astype(np.intp)
            cols = np.clip(pts[:, 1], 0, w - 1).astype(np.intp)
            inds = rows * w + cols
            flat[inds] = ce
