from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config, write_json
from .agent.report_writer import run_grounded_report
from .benchmarks import benchmark_suite
from .models import scenario_from_config
from .optimization import optimize_deployment
from .reporting import optimization_markdown, simulation_markdown
from .simulation import simulate_scenario


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rsagin")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--config", required=True)

    simulate_parser = subparsers.add_parser("simulate")
    simulate_parser.add_argument("--config", required=True)
    simulate_parser.add_argument("--out", required=True)
    simulate_parser.add_argument("--model-profile", default="closed_form_v0")
    simulate_parser.add_argument("--selected", nargs="*", default=[])

    optimize_parser = subparsers.add_parser("optimize")
    optimize_parser.add_argument("--config", required=True)
    optimize_parser.add_argument("--out", required=True)
    optimize_parser.add_argument("--model-profile", default="closed_form_v0")
    optimize_parser.add_argument("--solver", default=None)

    benchmark_parser = subparsers.add_parser("benchmark")
    benchmark_parser.add_argument("--config", required=True)
    benchmark_parser.add_argument("--out", required=True)
    benchmark_parser.add_argument("--model-profile", default="closed_form_v0")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--config", required=True)
    report_parser.add_argument("--out", required=True)
    report_parser.add_argument("--model-profile", default="standards_l1")
    report_parser.add_argument("--template", default="enterprise", choices=["research", "enterprise", "grant"])
    report_parser.add_argument("--selected", nargs="*", default=[])

    args = parser.parse_args(argv)

    if args.command == "validate":
        scenario = scenario_from_config(load_config(args.config))
        print(f"OK: {scenario.id} with {len(scenario.fixed_nodes)} fixed and {len(scenario.candidate_nodes)} candidates")
        return 0

    if args.command == "simulate":
        scenario = scenario_from_config(load_config(args.config))
        run = simulate_scenario(
            scenario,
            selected_candidate_ids=args.selected,
            model_profile=args.model_profile,
        )
        out_dir = Path(args.out)
        _write_simulation(out_dir, run)
        print(f"Wrote simulation run to {out_dir}")
        return 0

    if args.command == "optimize":
        scenario = scenario_from_config(load_config(args.config))
        run = optimize_deployment(scenario, model_profile=args.model_profile, solver=args.solver)
        out_dir = Path(args.out)
        _write_optimization(out_dir, run)
        print(f"Wrote optimization run to {out_dir}")
        return 0

    if args.command == "benchmark":
        scenario = scenario_from_config(load_config(args.config))
        suite = benchmark_suite(scenario, model_profile=args.model_profile)
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        write_json(out_dir / "benchmark.json", suite)
        print(f"Wrote benchmark suite to {out_dir}")
        return 0

    if args.command == "report":
        scenario = scenario_from_config(load_config(args.config))
        run = simulate_scenario(
            scenario,
            selected_candidate_ids=args.selected,
            model_profile=args.model_profile,
        )
        report = run_grounded_report(run, scenario, template=args.template)
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        write_json(out_dir / f"report_{args.template}.json", report)
        (out_dir / f"report_{args.template}.md").write_text(report["executive_summary"], encoding="utf-8")
        print(f"Wrote {args.template} report to {out_dir}")
        return 0

    raise AssertionError(args.command)


def _write_simulation(out_dir: Path, run) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "summary.json", run.summary)
    write_json(out_dir / "run.json", run.model_dump(mode="json"))
    for name, layer in run.layers.items():
        write_json(out_dir / f"{name}_layer.json", layer.model_dump(mode="json"))
    (out_dir / "report.md").write_text(simulation_markdown(run), encoding="utf-8")


def _write_optimization(out_dir: Path, run) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "optimization.json", run.model_dump(mode="json"))
    write_json(out_dir / "summary.json", run.summary)
    write_json(out_dir / "baseline_run.json", run.baseline_run.model_dump(mode="json"))
    write_json(out_dir / "optimized_run.json", run.optimized_run.model_dump(mode="json"))
    (out_dir / "report.md").write_text(optimization_markdown(run), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
