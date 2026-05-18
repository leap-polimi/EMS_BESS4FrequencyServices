"""Run the Italian BESS optimization model over multiple input days and EPR values.

Example
-------
python src/ITA_BESS_optimizer_run.py \
    --input-dir Data/Italy/input_data \
    --output-dir results/ITALY/Optimization_Results \
    --solver gurobi \
    --epr-values 1 2 4 6 8

Each input file is expected to be a Pyomo `.dat` file whose name contains the
calendar date in the original pattern used by the study, for example:
`input_data_2023_01_01.dat`. The script creates one pickle file per day and EPR.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cloudpickle
import pyomo.environ as pyo
import pyomo.opt

import ITA_BESS_optimizer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Italian BESS MILP cases.")
    parser.add_argument("--input-dir", default="Data/Italy/input_data", help="Directory containing Pyomo .dat input files.")
    parser.add_argument("--output-dir", default="results/ITALY/Optimization_Results", help="Directory where optimized Pyomo instances are written as .pkl files.")
    parser.add_argument("--solver", default="gurobi", help="Pyomo solver name, e.g. gurobi, cplex, highs, glpk.")
    parser.add_argument("--epr-values", nargs="+", type=float, default=[1, 2, 4, 6, 8], help="Energy-to-power ratios to simulate.")
    parser.add_argument("--mipgap", type=float, default=1e-2, help="MILP relative optimality gap.")
    parser.add_argument("--time-limit", type=int, default=3600, help="Solver time limit in seconds.")
    parser.add_argument("--tee", action="store_true", help="Print full solver log.")
    return parser.parse_args()


def extract_date_token(path: Path) -> str:
    parts = path.stem.split("_")
    if len(parts) < 6:
        raise ValueError(f"Cannot extract date from {path.name}; expected at least six underscore-separated fields.")
    return f"{parts[3]}_{parts[4]}_{parts[5]}"


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_files = sorted(p for p in input_dir.iterdir() if p.is_file())
    if not input_files:
        raise FileNotFoundError(f"No input files found in {input_dir.resolve()}")

    for input_file in input_files:
        date_token = extract_date_token(input_file)
        print(f"Loading Italian input data for {date_token}: {input_file}")

        for epr in args.epr_values:
            data = pyo.DataPortal(model=ITA_BESS_optimizer.model)
            data.load(filename=str(input_file))
            data.data()["EPR"] = {None: epr}

            instance = ITA_BESS_optimizer.model.create_instance(data)
            solver = pyomo.opt.SolverFactory(args.solver)
            solver.options["mipgap"] = args.mipgap
            solver.options["timelimit"] = args.time_limit

            results = solver.solve(instance, symbolic_solver_labels=True, tee=args.tee, report_timing=True)
            print(results.solver.status, results.solver.termination_condition)

            epr_label = int(epr) if float(epr).is_integer() else epr
            output_file = output_dir / f"ITA_opt_results_{date_token}_EPR{epr_label}.pkl"
            with output_file.open("wb") as file:
                cloudpickle.dump(instance, file)
            print(f"Saved {output_file}")


if __name__ == "__main__":
    main()
