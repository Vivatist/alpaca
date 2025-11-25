"""
ALPACA RAG - Main entry point (deprecated, use worker.py instead)

This file is kept for backward compatibility.
All processing logic has been moved to worker.py
"""

if __name__ == "__main__":
    print("=" * 60)
    print("DEPRECATED: main.py is no longer used")
    print("=" * 60)
    print()
    print("Please use worker.py instead:")
    print("  python worker.py")
    print()
    print("Architecture has changed:")
    print("  - File Watcher: monitors files and provides API")
    print("  - Worker: processes files from queue")
    print("  - Admin Backend: provides REST API for monitoring")
    print()
    print("=" * 60)
