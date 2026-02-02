#!/usr/bin/env python3
"""
Development startup script.

Starts both the agent service and mock merchant in development mode.
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import fastapi
        import uvicorn
        import httpx
        import cryptography
        print("✓ All core dependencies installed")
        return True
    except ImportError as e:
        print(f"✗ Missing dependency: {e.name}")
        print("\nRun: pip install -r requirements.txt")
        return False


def check_keys():
    """Check if TAP keys exist."""
    keys_dir = PROJECT_ROOT / "config" / "keys"
    private_key = keys_dir / "agent_private.pem"
    public_key = keys_dir / "agent_public.pem"

    if private_key.exists() and public_key.exists():
        print("✓ TAP keys found")
        return True
    else:
        print("✗ TAP keys not found")
        print("\nRun: python scripts/generate_keys.py")
        return False


def check_env():
    """Check if .env file exists."""
    env_file = PROJECT_ROOT / "config" / ".env"
    env_example = PROJECT_ROOT / "config" / ".env.example"

    if env_file.exists():
        print("✓ Configuration file found")
        return True
    elif env_example.exists():
        print("! Configuration file not found, copying from example...")
        import shutil
        shutil.copy(env_example, env_file)
        print("✓ Created config/.env from example")
        print("  Please edit config/.env with your settings")
        return True
    else:
        print("✗ No configuration file found")
        return False


def start_services():
    """Start both services in development mode."""
    processes = []

    try:
        # Start Mock Merchant
        print("\n🏪 Starting Mock Merchant on http://localhost:8001 ...")
        merchant_process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "app.main:app",
                "--reload",
                "--host", "0.0.0.0",
                "--port", "8001",
            ],
            cwd=PROJECT_ROOT / "mock-merchant",
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "shared")},
        )
        processes.append(merchant_process)

        # Wait a bit for merchant to start
        time.sleep(2)

        # Start Agent Service
        print("🤖 Starting Agent Service on http://localhost:8000 ...")
        agent_process = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "app.main:app",
                "--reload",
                "--host", "0.0.0.0",
                "--port", "8000",
            ],
            cwd=PROJECT_ROOT / "agent-service",
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "shared")},
        )
        processes.append(agent_process)

        print("\n" + "=" * 60)
        print("Services started successfully!")
        print("=" * 60)
        print("\n📍 Agent UI:      http://localhost:8000")
        print("📍 Merchant Site: http://localhost:8001")
        print("📍 Agent API:     http://localhost:8000/docs")
        print("📍 Merchant API:  http://localhost:8001/docs")
        print("\nPress Ctrl+C to stop all services")
        print("=" * 60)

        # Wait for processes
        for p in processes:
            p.wait()

    except KeyboardInterrupt:
        print("\n\nShutting down services...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.wait()
        print("All services stopped.")


def main():
    print("=" * 60)
    print("Visa Agentic Commerce - Development Server")
    print("=" * 60)

    # Pre-flight checks
    print("\nRunning pre-flight checks...")

    if not check_dependencies():
        sys.exit(1)

    if not check_keys():
        response = input("\nGenerate keys now? [Y/n]: ")
        if response.lower() != "n":
            subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "generate_keys.py")])
        else:
            print("Keys are required. Exiting.")
            sys.exit(1)

    if not check_env():
        sys.exit(1)

    print("\n✓ All checks passed!")

    # Start services
    start_services()


if __name__ == "__main__":
    main()
