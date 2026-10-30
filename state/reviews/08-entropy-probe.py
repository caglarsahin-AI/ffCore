import random, string
from ffcore.guardrails.rules import find_secrets, is_plain_identifier
rng = random.Random(11)
def rnd(alpha, n): return "".join(rng.choice(alpha) for _ in range(n))
N = 4000
def rate(gen):
    exempt = caught = 0
    for _ in range(N):
        s = gen()
        if is_plain_identifier(s): exempt += 1
        if find_secrets(s): caught += 1
    return f"exempt={exempt/N:.3f} caught_by_secrets={caught/N:.3f}"
lower = string.ascii_lowercase
print("lower 2x12:", rate(lambda: "-".join(rnd(lower,12) for _ in range(2))))
print("lower 3x12:", rate(lambda: "-".join(rnd(lower,12) for _ in range(3))))
print("upper 3x6 :", rate(lambda: "-".join(rnd(string.ascii_uppercase,6) for _ in range(3))))
print("upper 2x6 :", rate(lambda: "_".join(rnd(string.ascii_uppercase,6) for _ in range(2))))
print("mixed 3x12:", rate(lambda: "-".join(rnd(string.ascii_letters+string.digits,12) for _ in range(3))))
names = ["SZL-2025-003_temizlik-hizmet","SZL-2024-011_cihaz-bakim","SZL-2025-007_laboratuvar-kiti","SZL-2025-012_yonetim-danismanlik","SZL-2023-019_yazilim-lisans","PRSIM-1234_kullanici-talebi","HBYS-2024_hasta-kayit-prosedur","yonetim-danismanlik-sozlesmesi","temizlik-hizmet-raporu-2025","strengths-report-final-v2"]
for n in names: print("name", n, "plain=", is_plain_identifier(n), "caught=", bool(find_secrets(n)))
