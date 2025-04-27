#!/usr/bin/env python3
import math
import random
import statistics
from collections import deque
import matplotlib.pyplot as plt

# ----------------- Helpers -----------------

def compute_k(n_peers, nines):
    """
    Compute k for a one-shot k-out overlay so that failure ≤ 10^(-nines):
        k ≥ ln(n_peers) + nines * ln(10)

    Args:
        n_peers (int): total number of peers
        nines   (int): reliability in nines (e.g. 3 for 10^-3)

    Returns:
        int: the fan-out k, clamped to [1, n_peers]
    """
    # trivial cases
    if n_peers <= 1 or nines is None:
        return n_peers

    # static overlay formula
    k = math.ceil(math.log(n_peers) + nines * math.log(10))

    # can’t pick more than N peers
    return min(n_peers, max(1, k))

def build_overlay(n_peers, k):
    """
    Static directed overlay: each node i picks k distinct targets.
    Returns adjacency list graph[i] = [v1, v2, ...].
    """
    nodes = list(range(n_peers))
    graph = {}
    for i in nodes:
        choices = nodes.copy()
        choices.remove(i)
        graph[i] = random.sample(choices, k)
    return graph

def propagate(graph):
    """
    BFS from node 0 over directed edges.
    Returns:
      - rounds = max hop-distance to reach all reachable nodes
      - total_msgs = # of pushes = (# of reached nodes) * k
      - dist_list = distance per node (–1 if unreachable)
    """
    n = len(graph)
    visited = [False]*n
    dist = [-1]*n
    q = deque()
    visited[0] = True
    dist[0] = 0
    q.append(0)

    while q:
        u = q.popleft()
        for v in graph[u]:
            if not visited[v]:
                visited[v] = True
                dist[v] = dist[u] + 1
                q.append(v)

    reached = sum(1 for x in visited if x)
    k = len(graph[0])
    total_msgs = reached * k
    rounds = max(dist) if reached == n else None
    return rounds, total_msgs, dist

# ----------------- Experiment -----------------

def main():
    # parameters
    N_values    = [100, 1_000, 10_000]
    nines_list  = [5, 7, 9]
    reps        = 3
    per_msg_latency = 0.001   # 1 ms per message
    packet_size     = 1024    # bytes per message

    # storage
    results = {
      'fullmesh': {'rounds': [], 'msgs': [], 'time': []},
      **{n: {'rounds': [], 'msgs': [], 'time': []} for n in nines_list}
    }

    # run sims
    for N in N_values:
        # full-mesh: 1 round, (N-1) messages from node0
        fm_rounds = 1
        fm_msgs   = N-1
        fm_time   = fm_msgs * per_msg_latency

        results['fullmesh']['rounds'].append(fm_rounds)
        results['fullmesh']['msgs'].append(fm_msgs)
        results['fullmesh']['time'].append(fm_time)

        for nines in nines_list:
            ks = []
            rs = []
            ms = []
            ts = []
            for _ in range(reps):
                k = compute_k(N, nines)
                graph = build_overlay(N, k)
                r, m, _ = propagate(graph)
                t = m * per_msg_latency
                ks.append(k); rs.append(r); ms.append(m); ts.append(t)
            results[nines]['rounds'].append(statistics.mean(rs))
            results[nines]['msgs'].append(statistics.mean(ms))
            results[nines]['time'].append(statistics.mean(ts))

    # ----------------- Plots -----------------

    # 1) Rounds vs N
    plt.figure()
    for nines in nines_list:
        plt.plot(N_values, results[nines]['rounds'], label=f'gossip ({nines}-nines)')
    plt.plot(N_values, results['fullmesh']['rounds'], '--', label='full-mesh')
    plt.xscale('log'); plt.yscale('log')
    plt.xlabel('Peers (N)'); plt.ylabel('Rounds')
    plt.title('Static k-Gossip Rounds vs Network Size')
    plt.legend()

    # 2) Messages vs N
    plt.figure()
    for nines in nines_list:
        plt.plot(N_values, results[nines]['msgs'], label=f'gossip ({nines}-nines)')
    plt.plot(N_values, results['fullmesh']['msgs'], '--', label='full-mesh')
    plt.xscale('log'); plt.yscale('log')
    plt.xlabel('Peers (N)'); plt.ylabel('Total Messages')
    plt.title('Static k-Gossip Messages vs Network Size')
    plt.legend()

    # 3) Time vs N
    plt.figure()
    for nines in nines_list:
        plt.plot(N_values, results[nines]['time'], label=f'gossip ({nines}-nines)')
    plt.plot(N_values, results['fullmesh']['time'], '--', label='full-mesh')
    plt.xscale('log'); plt.yscale('log')
    plt.xlabel('Peers (N)'); plt.ylabel('Time (s)')
    plt.title(f'Propagation Time (@{per_msg_latency*1000:.0f}ms/msg)')
    plt.legend()

    # 4) Histogram at N=100 for bytes per peer
    N_hist, n9 = 100, 5
    k_hist = compute_k(N_hist, n9)
    # full-mesh per-peer bytes
    fm_bytes = [ (N_hist-1)*packet_size ] + [0]*(N_hist-1)
    # gossip per-peer bytes (each peer sends exactly k once)
    kg_bytes = [k_hist*packet_size]*N_hist
    print(fm_bytes)
    print(kg_bytes)

    plt.figure()
    plt.hist(fm_bytes, bins=100, alpha=0.6, label='full-mesh')
    plt.hist(kg_bytes, bins=100, alpha=0.6, label=f'gossip ({n9}-nines)')
    plt.xlabel('Bytes Sent Per Peer')
    plt.ylabel('Number of Peers')
    plt.title(f'Per-Peer Bytes (N={N_hist})')
    plt.legend()

    plt.show()

if __name__ == "__main__":
    main()
