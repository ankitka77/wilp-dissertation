from __future__ import annotations

import argparse
from pathlib import Path
import logging

from phase9.config.loader import load_config
from phase9.logging.logger import configure_logging, get_logger
from phase9.pipeline import Phase9Pipeline
from phase9.utils.jsonyaml import dump_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase9_runner.py")
    sub = parser.add_subparsers(dest="command")

    # Define all subcommands (Stage 2)
    discover = sub.add_parser("discover", help="Discover upstream artifacts and parse manifests")
    discover.add_argument("--phase", "-p", nargs="*", type=int, help="phases to discover (e.g. 5 6 7)")
    discover.add_argument("--config", "-c", type=Path, help="path to config YAML")
    discover.add_argument("--output", "-o", type=Path, help="output directory for phase9 artifacts")
    discover.add_argument("--verbose", "-v", action="store_true")
    discover.add_argument("--log-level", type=str, help="override log level")

    aggregate = sub.add_parser("aggregate", help="Aggregate metadata and compute metrics")
    aggregate.add_argument("--phase", "-p", nargs="*", type=int, help="phases to aggregate (e.g. 5 6 7)")
    aggregate.add_argument("--config", "-c", type=Path, help="path to config YAML")
    aggregate.add_argument("--output", "-o", type=Path, help="output directory for phase9 artifacts")
    aggregate.add_argument("--strict", action="store_true", help="treat warnings as errors")
    aggregate.add_argument("--verbose", "-v", action="store_true")
    aggregate.add_argument("--log-level", type=str, help="override log level")

    validate = sub.add_parser("validate", help="Validate discovered artifacts and build registry")
    validate.add_argument("--phase", "-p", nargs="*", type=int, help="phases to validate (e.g. 5 6 7)")
    validate.add_argument("--config", "-c", type=Path, help="path to config YAML")
    validate.add_argument("--output", "-o", type=Path, help="output directory for phase9 artifacts")
    validate.add_argument("--strict", action="store_true", help="treat warnings as errors")
    validate.add_argument("--verbose", "-v", action="store_true")
    validate.add_argument("--log-level", type=str, help="override log level")

    generate = sub.add_parser("generate-assets", help="Generate reporting tables and figures")
    generate.add_argument("--phase", "-p", nargs="*", type=int, help="phases to include (e.g. 5 6 7)")
    generate.add_argument("--config", "-c", type=Path, help="path to config YAML")
    generate.add_argument("--output", "-o", type=Path, help="output directory for phase9 artifacts")
    generate.add_argument("--strict", action="store_true", help="treat warnings as errors")
    generate.add_argument("--verbose", "-v", action="store_true")
    generate.add_argument("--log-level", type=str, help="override log level")

    generate_report = sub.add_parser("generate-report", help="Generate reports and package Phase 9 outputs")
    generate_report.add_argument("--phase", "-p", nargs="*", type=int, help="phases to include (e.g. 5 6 7)")
    generate_report.add_argument("--config", "-c", type=Path, help="path to config YAML")
    generate_report.add_argument("--output", "-o", type=Path, help="output directory for phase9 artifacts")
    generate_report.add_argument("--strict", action="store_true", help="treat warnings as errors")
    generate_report.add_argument("--verbose", "-v", action="store_true")
    generate_report.add_argument("--log-level", type=str, help="override log level")

    run_cmd = sub.add_parser("run", help="Run the complete Phase 9 workflow and write reproducibility artifacts")
    run_cmd.add_argument("--phase", "-p", nargs="*", type=int, help="phases to include (e.g. 5 6 7)")
    run_cmd.add_argument("--config", "-c", type=Path, help="path to config YAML")
    run_cmd.add_argument("--output", "-o", type=Path, help="output directory for phase9 artifacts")
    run_cmd.add_argument("--strict", action="store_true", help="treat warnings as errors")
    run_cmd.add_argument("--verbose", "-v", action="store_true")
    run_cmd.add_argument("--log-level", type=str, help="override log level")

    # Stage 3: parse args once
    args = parser.parse_args(argv)

    # Stage 4: load configuration and logging
    cfg = load_config(args.config) if getattr(args, "config", None) else load_config()
    if getattr(args, "log_level", None):
        cfg.logging.level = args.log_level

    configure_logging(cfg)
    logger = get_logger("phase9.runner")

    pipeline = Phase9Pipeline(cfg)

    # Stage 5: dispatch
    if args.command == "discover":
        phases = args.phase if args.phase else None
        try:
            pipeline.initialize_logging(level=args.log_level if args.log_level else None)
            pipeline.discover(phases=phases, output_dir=args.output)
            logger.info("Discovery complete.")
            return 0
        except Exception as e:
            logger.exception("Discovery failed: %s", e)
            return 2

    if args.command == "validate":
        phases = args.phase if args.phase else None
        try:
            pipeline.initialize_logging(level=args.log_level if args.log_level else None)
            code = pipeline.validate(phases=phases, strict=args.strict, output_dir=args.output)
            return code
        except Exception as e:
            logger.exception("Validation failed: %s", e)
            return 2

    if args.command == "aggregate":
        phases = args.phase if args.phase else None
        try:
            pipeline.initialize_logging(level=args.log_level if args.log_level else None)
            code = pipeline.aggregate(phases=phases, strict=args.strict, output_dir=args.output)
            return code
        except Exception as e:
            logger.exception("Aggregate failed: %s", e)
            return 2

    if args.command == "generate-assets":
        phases = args.phase if args.phase else None
        try:
            pipeline.initialize_logging(level=args.log_level if args.log_level else None)
            code = pipeline.aggregate(phases=phases, strict=args.strict, output_dir=args.output)
            return code
        except Exception as e:
            logger.exception("generate-assets failed: %s", e)
            return 2

    if args.command == "generate-report":
        phases = args.phase if args.phase else None
        try:
            pipeline.initialize_logging(level=args.log_level if args.log_level else None)
            code = pipeline.generate_report(phases=phases, strict=args.strict, output_dir=args.output)
            return code
        except Exception as e:
            logger.exception("generate-report failed: %s", e)
            return 2

    if args.command == "run":
        phases = args.phase if args.phase else None
        try:
            pipeline.initialize_logging(level=args.log_level if args.log_level else None)
            code = pipeline.run(phases=phases, strict=args.strict, output_dir=args.output, config_path=args.config)
            return code
        except Exception as e:
            logger.exception("Run failed: %s", e)
            return 2

    parser.print_usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
