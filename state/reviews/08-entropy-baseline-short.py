import random, string
from ffcore.guardrails.rules import find_secrets
rng = random.Random(11)
def rnd(alpha, n): return "".join(rng.choice(alpha) for _ in range(n))
N = 4000
L, U = string.ascii_lowercase, string.ascii_uppercase
def caught_rate(gen):
    return sum(bool(find_secrets(gen())) for _ in range(N)) / N
print("lower 5x3 caught:", caught_rate(lambda: "-".join(rnd(L,3) for _ in range(5))))
print("upper 5x3 caught:", caught_rate(lambda: "-".join(rnd(U,3) for _ in range(5))))
print("lower 2x12 caught:", caught_rate(lambda: "-".join(rnd(L,12) for _ in range(2))))
print("upper 2x6 caught:", caught_rate(lambda: "_".join(rnd(U,6) for _ in range(2))))
