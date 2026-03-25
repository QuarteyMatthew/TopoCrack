import numpy as np
from numba import jit, njit
import networkx as nx

# ========== 2D ONLY ==========

@njit
def neighbors(shape):
    h, w = shape

    # 8-neighborhood (dr, dc)
    dr = np.array([-1, -1, -1, 0, 0, 1, 1, 1], dtype=np.int64)
    dc = np.array([-1,  0,  1,-1, 1,-1, 0, 1], dtype=np.int64)

    # convert to linear offsets
    nbs = dr * w + dc
    return nbs


@jit  # my mark
def mark(img):  # mark the array use (0, 1, 2)
    nbs = neighbors(img.shape)
    img = img.ravel()
    for p in range(len(img)):
        if img[p] == 0:
            continue
        s = 0
        for dp in nbs:
            if img[p + dp] != 0:
                s += 1
        if s == 2:
            img[p] = 1
        else:
            img[p] = 2


@jit  # trans index to r, c...
def idx2rc(idx, acc):
    rst = np.zeros((len(idx), len(acc)), dtype=np.int16)
    for i in range(len(idx)):
        for j in range(len(acc)):
            rst[i, j] = idx[i] // acc[j]
            idx[i] -= rst[i, j] * acc[j]
    rst -= 1
    return rst


@jit  # fill a node (may be two or more points)
def fill(img, p, num, nbs, acc, buf):
    back = img[p]
    img[p] = num
    buf[0] = p
    cur = 0
    s = 1

    while True:
        p = buf[cur]
        for dp in nbs:
            cp = p + dp
            if img[cp] == back:
                img[cp] = num
                buf[s] = cp
                s += 1
        cur += 1
        if cur == s:
            break
    return idx2rc(buf[:s], acc)


@jit  # trace the edge and use a buffer, then buf.copy, if use [] numba not works
def trace(img, p, nbs, acc, buf):
    c1 = 0
    c2 = 0
    newp = 0
    cur = 0

    while True:
        buf[cur] = p
        img[p] = 0
        cur += 1
        for dp in nbs:
            cp = p + dp
            if img[cp] >= 10:
                if c1 == 0:
                    c1 = img[cp]
                else:
                    c2 = img[cp]
            if img[cp] == 1:
                newp = cp
        p = newp
        if c2 != 0:
            break
    return (c1 - 10, c2 - 10, idx2rc(buf[:cur], acc))


@jit  # parse the image then get the nodes and edges
def parse_struc(img):
    nbs = neighbors(img.shape)

    # acc come array int64 compatibile con numba
    shape_vec = np.array((1,) + img.shape[::-1][:-1], dtype=np.int64)
    acc = np.cumprod(shape_vec)[::-1]

    img = img.ravel()

    # raccogli gli indici dei pixel == 2 in un buffer preallocato
    total = len(img)
    pts_buf = np.zeros(total, dtype=np.int64)
    cnt = 0
    for i in range(total):
        if img[i] == 2:
            pts_buf[cnt] = i
            cnt += 1

    buf = np.zeros(131072, dtype=np.int64)
    num = 10
    nodes = []
    # usa solo i primi cnt elementi di pts_buf
    for k in range(cnt):
        p = pts_buf[k]
        if img[p] == 2:
            nds = fill(img, p, num, nbs, acc, buf)
            num += 1
            nodes.append(nds)

    edges = []
    for k in range(cnt):
        p = pts_buf[k]
        for dp in nbs:
            if img[p + dp] == 1:
                edge = trace(img, p + dp, nbs, acc, buf)
                edges.append(edge)
    return nodes, edges


# use nodes and edges build a networkx graph
def build_graph(nodes, edges, multi=False):
    graph = nx.MultiGraph() if multi else nx.Graph()
    for i in range(len(nodes)):
        graph.add_node(i, pts=nodes[i], o=nodes[i].mean(axis=0))
    for s, e, pts in edges:
        l = np.linalg.norm(pts[1:] - pts[:-1], axis=1).sum()
        graph.add_edge(s, e, pts=pts, weight=l)
    return graph


def buffer(ske):
    buf = np.zeros(tuple(np.array(ske.shape) + 2), dtype=np.uint16)
    buf[tuple([slice(1, -1)] * buf.ndim)] = ske
    return buf


def build_sknw(ske, multi=False):
    buf = buffer(ske)
    mark(buf)
    nodes, edges = parse_struc(buf)
    return build_graph(nodes, edges, multi)


# draw the graph
def draw_graph(img, graph, cn=255, ce=128):
    acc = np.cumprod((1,) + img.shape[::-1][:-1])[::-1]
    img = img.ravel()
    for idx in graph.nodes():
        pts = graph.nodes[idx]['pts']
        img[np.dot(pts, acc)] = cn
    for (s, e) in graph.edges():
        eds = graph[s][e]
        for i in eds:
            pts = eds[i]['pts']
            img[np.dot(pts, acc)] = ce


if __name__ == '__main__':
    g = nx.MultiGraph()
    g.add_nodes_from([1, 2, 3, 4, 5])
    g.add_edges_from([(1, 2), (1, 3), (2, 3), (4, 5), (5, 4)])
    print(g.nodes())
    print(g.edges())
    a = g.subgraph(1)
    print('d')
    print(a)
    print('d')
