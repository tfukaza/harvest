"""Standalone entry point: python -m harvest.debug."""


import argparse

from harvest.debug.registry import SandboxRegistry
from harvest.debug.server import DebugMonitorServer


def main() -> None:
    parser = argparse.ArgumentParser(description="Harvest Debug Monitor Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--static-dir", default=None)
    args = parser.parse_args()

    registry = SandboxRegistry()
    server = DebugMonitorServer(
        registry=registry,
        host=args.host,
        port=args.port,
        static_dir=args.static_dir,
    )
    print(f"Debug monitor server starting on http://{args.host}:{args.port}")
    server.start()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.stop()


if __name__ == "__main__":
    main()
