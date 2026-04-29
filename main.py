#!/usr/bin/env python3
"""
Start both servers:
  Webapp        → http://localhost:8000
  Agent router  → http://localhost:3002
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def main():
    webapp = subprocess.Popen(
        [PY, "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=ROOT / "webapp",
    )
    agent = subprocess.Popen(
        [PY, "-m", "uvicorn", "agent_router.agent_router:app", "--host", "0.0.0.0", "--port", "3002", "--reload"],
        cwd=ROOT / "langgraph",
    )

    print("Webapp:       http://localhost:8000")
    print("Agent router: http://localhost:3002")
    print("Ctrl+C to stop both.\n")

    try:
        while True:
            if webapp.poll() is not None:
                print("\nWebapp stopped — shutting down agent router.")
                agent.terminate()
                agent.wait()
                break
            if agent.poll() is not None:
                print("\nAgent router stopped — shutting down webapp.")
                webapp.terminate()
                webapp.wait()
                break
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        webapp.terminate()
        agent.terminate()
        webapp.wait()
        agent.wait()


if __name__ == "__main__":
    main()
