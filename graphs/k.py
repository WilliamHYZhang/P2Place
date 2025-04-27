import math
import matplotlib.pyplot as plt

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

N_values = range(2, 1001)
nines_list = [1, 5, 10]

plt.figure()
for nines in nines_list:
    k_values = [compute_k(N, nines) for N in N_values]
    plt.plot(N_values, k_values, label=f'nines={nines}')

plt.xlabel('Number of Peers (N)')
plt.ylabel('k')
plt.legend()
plt.grid(True)
plt.show()