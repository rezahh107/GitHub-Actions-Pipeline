#!/usr/bin/env python3
from __future__ import annotations
import argparse,sys
from pathlib import Path
if __package__ in (None,""):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.ci_models import serialize_report
from tools.ci_outcome_registry import build_profile_evolution_proposals,load_outcomes
from tools.ci_upgrade_models import UpgradeContractError

def main()->int:
    parser=argparse.ArgumentParser(description="Produce review-only profile evolution proposals from exact-head validated outcomes.")
    parser.add_argument("--outcomes",required=True);parser.add_argument("--out",required=True);parser.add_argument("--minimum-distinct-repositories",type=int,default=3);args=parser.parse_args()
    try:
        result=build_profile_evolution_proposals(load_outcomes(Path(args.outcomes)),minimum_distinct_repositories=args.minimum_distinct_repositories);Path(args.out).write_text(serialize_report(result),encoding="utf-8")
    except UpgradeContractError as exc:print(f"{exc.code}: {exc.message}",file=sys.stderr);return 3
    except OSError as exc:print(f"PROFILE_EVOLUTION_WRITE_FAILED: {exc}",file=sys.stderr);return 4
    print(f"Wrote {len(result['proposals'])} review-only profile evolution proposals to {args.out}");return 0
if __name__=="__main__":raise SystemExit(main())
