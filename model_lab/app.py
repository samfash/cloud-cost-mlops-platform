"""Lightweight Flask API for trial selection."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request

from model_lab.selector import select_chosen_trial

LAB_ROOT = Path(__file__).resolve().parent
app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "model-lab"})


@app.post("/api/select")
def select():
    payload = request.get_json(silent=True) or {}
    trials_dir = Path(payload.get("trials_dir", LAB_ROOT / "trials"))
    constraints = Path(payload.get("constraints_path", LAB_ROOT / "constraints.yaml"))
    chosen = select_chosen_trial(trials_dir, constraints)
    return jsonify({"status": "success", "chosen": chosen})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
