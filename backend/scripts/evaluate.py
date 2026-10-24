"""python -m scripts.evaluate   (run from backend/) -> writes artifacts/evaluation.json"""
from app.data import load_dataset
from app.evaluation import run_protocol, save

if __name__ == "__main__":
    report = run_protocol(load_dataset())
    save(report)
    print("\nSaved evaluation.json")
