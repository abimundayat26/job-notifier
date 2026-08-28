import logging
import sys
import argparse

from jobnotifier.config import load_config
from jobnotifier.pipeline import run_pipeline

CONFIG_PATH = "config/config.yaml"


def main(config_path: str = CONFIG_PATH) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = load_config(config_path)
    run_pipeline(config)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=str,
        default=CONFIG_PATH,
        help="Path to the config file (default: %(default)s)",
    )
    args = parser.parse_args()
    sys.exit(main(config_path=args.config))
