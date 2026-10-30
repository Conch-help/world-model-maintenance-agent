"""Command-line entry points for the maintenance agent."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np

from .config import PROJECT_ROOT, load_config
from .data import collect_transitions
from .evaluation import (
    EvaluationResult,
    HighFidelityOraclePolicy,
    WorldModelPolicy,
    evaluate_policy,
    evaluate_world_model,
    fixed_interval_policy,
    full_policy,
    threshold_policy,
)
from .world_model import EnsembleWorldModel


ARTIFACTS = PROJECT_ROOT / "artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    raise TypeError(type(value).__name__)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")


def train(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    train_cfg = cfg["world_model"]
    eval_cfg = cfg["evaluation"]
    plant_cfg = cfg["plant"]
    print("[1/3] collecting transitions from independent high-fidelity plant ...")
    dataset = collect_transitions(
        n_episodes=int(args.episodes or eval_cfg["train_episodes"]),
        episode_hours=int(args.hours or plant_cfg["episode_hours"]),
        seed=int(args.seed or plant_cfg["seed"]),
    )
    print(f"      transitions: {dataset.n_samples}")
    print("[2/3] fitting action-conditioned ensemble world model ...")
    model = EnsembleWorldModel(
        n_machines=int(plant_cfg["n_machines"]),
        ensemble_size=int(train_cfg["ensemble_size"]),
        hidden=int(train_cfg["hidden"]),
        seed=int(args.seed or plant_cfg["seed"]),
    )
    fit = model.fit(
        dataset.states,
        dataset.actions,
        dataset.next_states,
        dataset.profits,
        dataset.productions,
        epochs=int(args.epochs or train_cfg["epochs"]),
        batch_size=int(train_cfg["batch_size"]),
        lr=float(train_cfg["learning_rate"]),
    )
    model_path = ARTIFACTS / "world_model.npz"
    model.save(model_path)
    metrics = evaluate_world_model(model)
    report = {
        "dataset": {"n_episodes": int(args.episodes or eval_cfg["train_episodes"]), "n_transitions": dataset.n_samples},
        "fit": fit,
        "heldout": metrics,
        "model_path": str(model_path),
    }
    _write_json(ARTIFACTS / "training_report.json", report)
    print(f"[3/3] saved {model_path}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _evaluate_all(model: EnsembleWorldModel, cfg: dict, seeds_override: list[int] | None = None) -> dict[str, EvaluationResult]:
    plant_cfg = cfg["plant"]
    planner_cfg = cfg["planner"]
    eval_cfg = cfg["evaluation"]
    seeds = seeds_override or list(eval_cfg["seeds"])
    hours = int(plant_cfg["episode_hours"])
    results = {
        "full_production": evaluate_policy("full_production", seeds, hours, lambda: full_policy),
        "fixed_interval": evaluate_policy("fixed_interval", seeds, hours, lambda: fixed_interval_policy(72)),
        "threshold_maintenance": evaluate_policy("threshold_maintenance", seeds, hours, lambda: threshold_policy),
        "world_model_only": evaluate_policy(
            "world_model_only",
            seeds,
            hours,
            lambda: WorldModelPolicy(
                model,
                plan_every=int(planner_cfg["replan_every"]),
                verify_candidates=0,
                horizon=int(planner_cfg["horizon"]),
                population=int(planner_cfg["population"]),
                elite=int(planner_cfg["elite"]),
                iterations=int(planner_cfg["iterations"]),
            ),
        ),
        "highfidelity_oracle": evaluate_policy(
            "highfidelity_oracle",
            seeds,
            hours,
            lambda: HighFidelityOraclePolicy(
                plan_every=int(planner_cfg["replan_every"]),
                horizon=12,
                population=12,
                elite=4,
                iterations=2,
            ),
        ),
        "world_model_robust_mpc": evaluate_policy(
            "world_model_robust_mpc",
            seeds,
            hours,
            lambda: WorldModelPolicy(
                model,
                plan_every=int(planner_cfg["replan_every"]),
                verify_candidates=4,
                horizon=int(planner_cfg["horizon"]),
                population=int(planner_cfg["population"]),
                elite=int(planner_cfg["elite"]),
                iterations=int(planner_cfg["iterations"]),
                robust_verify=True,
                safety_shield_enabled=True,
            ),
        ),
        "world_model_verified_mpc": evaluate_policy(
            "world_model_verified_mpc",
            seeds,
            hours,
            lambda: WorldModelPolicy(
                model,
                plan_every=int(planner_cfg["replan_every"]),
                verify_candidates=1,
                horizon=int(planner_cfg["horizon"]),
                population=int(planner_cfg["population"]),
                elite=int(planner_cfg["elite"]),
                iterations=int(planner_cfg["iterations"]),
                robust_verify=False,
                safety_shield_enabled=False,
            ),
        ),
    }
    return results


def evaluate(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    model_path = Path(args.model) if args.model else ARTIFACTS / "world_model.npz"
    if not model_path.exists():
        raise SystemExit(f"model not found: {model_path}; run `python -m wm_maint.cli train` first")
    model = EnsembleWorldModel.load(model_path)
    seeds = [int(x) for x in args.seeds.split(",")] if args.seeds else None
    print(f"[1/2] evaluating {len(seeds) if seeds else len(cfg['evaluation']['seeds'])} seeds per policy ...")
    results = _evaluate_all(model, cfg, seeds)
    summary = {name: result.summary() for name, result in results.items()}
    baseline = summary["threshold_maintenance"]["profit_mean"]
    for name, row in summary.items():
        row["profit_delta_vs_threshold_pct"] = (
            (row["profit_mean"] - baseline) / max(1.0, abs(baseline)) * 100.0
        )
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model_path": str(model_path),
        "seeds": seeds or list(cfg["evaluation"]["seeds"]),
        "summary": summary,
        "plan_audits": [
            {
                "seed": a.seed,
                "hour": a.hour,
                "predicted_profit": a.predicted_profit,
                "verified_profit": a.verified_profit,
                "prediction_error": a.prediction_error,
                "verified_failures": a.verified_failures,
                "verified_unmet": a.verified_unmet,
                "capacity_violations": a.capacity_violations,
                "verified_robust_score": a.verified_robust_score,
                "verified_failure_probability": a.verified_failure_probability,
                "verified_failures_p90": a.verified_failures_p90,
                "verified_cvar10": a.verified_cvar10,
            }
            for a in results["world_model_verified_mpc"].plan_audits
        ],
    }
    out = ARTIFACTS / "evaluation_report.json"
    _write_json(out, payload)
    print(f"[2/2] wrote {out}")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


def demo(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    model_path = Path(args.model) if args.model else ARTIFACTS / "world_model.npz"
    if not model_path.exists():
        raise SystemExit(f"model not found: {model_path}; run train first")
    model = EnsembleWorldModel.load(model_path)
    seeds = [int(x) for x in args.seeds.split(",")] if args.seeds else [11]
    results = _evaluate_all(model, cfg, seeds)
    payload = {name: result.summary() for name, result in results.items()}
    _write_json(ARTIFACTS / "demo_report.json", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="World-model maintenance agent")
    parser.add_argument("--config", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("train", help="collect transitions and fit the ensemble world model")
    p.add_argument("--episodes", type=int)
    p.add_argument("--hours", type=int)
    p.add_argument("--epochs", type=int)
    p.add_argument("--seed", type=int)
    p.set_defaults(func=train)
    p = sub.add_parser("evaluate", help="run baselines and the verified world-model policy")
    p.add_argument("--model")
    p.add_argument("--seeds")
    p.set_defaults(func=evaluate)
    p = sub.add_parser("demo", help="compact demo report")
    p.add_argument("--model")
    p.add_argument("--seeds")
    p.set_defaults(func=demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
