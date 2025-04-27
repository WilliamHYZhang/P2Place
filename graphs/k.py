import math
import matplotlib.pyplot as plt

def compute_k(n_peers, nines):
    """
    Solve N^(2-2k) <= 10^-nines -> k >= 1 + (nines * ln10)/(2 ln N)
    """
    if n_peers <= 1 or nines is None:
        return min(n_peers, 3)
    raw = math.ceil(1 + (nines * math.log(10)) / (2 * math.log(n_peers)))
    return min(n_peers, raw)

N_values = range(2, 101)
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