import random, string
from ffcore.guardrails.rules import find_secrets, is_plain_identifier
rng = random.Random(11)
def rnd(alpha, n): return "".join(rng.choice(alpha) for _ in range(n))
N = 4000
def rate(gen):
    exempt = caught = 0
    for _ in range(N):
        s = gen()
        exempt += is_plain_identifier(s)
        caught += bool(find_secrets(s))
    return f"exempt={exempt/N:.3f} caught={caught/N:.3f}"
L, U = string.ascii_lowercase, string.ascii_uppercase
print("lower 2x12 :", rate(lambda: "-".join(rnd(L,12) for _ in range(2))))
print("upper 2x6  :", rate(lambda: "_".join(rnd(U,6) for _ in range(2))))
print("upper 3x6  :", rate(lambda: "-".join(rnd(U,6) for _ in range(3))))
print("lower 5x3  :", rate(lambda: "-".join(rnd(L,3) for _ in range(5))))
print("upper 5x3  :", rate(lambda: "-".join(rnd(U,3) for _ in range(5))))
print("upper 4x4  :", rate(lambda: "-".join(rnd(U,4) for _ in range(4))))
print("mixed 3x12 :", rate(lambda: "-".join(rnd(L+U+string.digits,12) for _ in range(3))))
