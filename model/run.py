"""Entry point: generate data, train, evaluate, or serve the API."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import argparse


def main():
    parser = argparse.ArgumentParser(description="Cellular Maze Model Pipeline")
    parser.add_argument("--generate", action="store_true", help="Generate synthetic data")
    parser.add_argument("--train", action="store_true", help="Train the model")
    parser.add_argument("--evaluate", action="store_true", help="Run comprehensive evaluation")
    parser.add_argument("--serve", action="store_true", help="Start FastAPI server")
    parser.add_argument("--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--epochs", type=int, default=None, help="Override training epochs")
    parser.add_argument("--device", default="auto", help="Device: auto, cpu, cuda")
    args = parser.parse_args()

    if not any([args.generate, args.train, args.evaluate, args.serve]):
        parser.print_help()
        return

    if args.generate:
        from model.generate_data import main as gen_main
        gen_main()

    if args.train:
        from model.train import train
        kwargs = {"device_name": args.device}
        if args.epochs:
            kwargs["epochs"] = args.epochs
        train(**kwargs)

    if args.evaluate:
        from model.evaluate import evaluate
        evaluate()

    if args.serve:
        import uvicorn
        uvicorn.run("model.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
