"""Run the lifecycle demo with a real LLM.

Usage:
    python demos/lifecycle/lifecycle_demo.py
"""
import asyncio
from pathlib import Path
from harvest.agent_sandbox.basic_sandbox import BasicSandbox

async def main():
    manifest_path = Path(__file__).parent / "lifecycle.yaml"
    sandbox = BasicSandbox.from_manifest(str(manifest_path))
    await sandbox.start()
    try:
        # Let agents run for up to 120 seconds
        await asyncio.sleep(120)
    except KeyboardInterrupt:
        pass
    finally:
        await sandbox.stop()
    print("Demo complete.")

if __name__ == "__main__":
    asyncio.run(main())
