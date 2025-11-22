#!/usr/bin/env python
"""
Скрипт для запуска Prefect flows с расписанием (Prefect 3.x)
"""

import asyncio
from app.workers.scheduler import serve_flows


async def main():
    """Запускает flows с расписанием"""
    print("🚀 Starting Prefect flows with schedules...")
    print("=" * 50)
    print()
    print("Flows will be running with the following schedules:")
    print("  - file_watcher_flow: every 60 seconds")
    print("  - main_orchestrator_flow: every 60 seconds")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 50)
    print()
    
    try:
        await serve_flows()
    except KeyboardInterrupt:
        print("\n\n👋 Stopping flows...")


if __name__ == "__main__":
    asyncio.run(main())
