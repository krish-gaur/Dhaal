from pathlib import Path
# routes/document.py path calculation
p = Path("routes/document.py").resolve().parent.parent.parent / "fixtures" / "policy_suraksha_shield.pdf"
print("routes path:", p, "exists:", p.exists())

# actual
p2 = Path(__file__).parent.parent.parent / "fixtures" / "policy_suraksha_shield.pdf"
print("api parent path:", p2, "exists:", p2.exists())
