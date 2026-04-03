#!/usr/bin/env python
"""Entrypoint script to start the FastAPI application."""
import sys
from pathlib import Path

if __name__ == "__main__":
    # Ensure the project root is on the Python path
    project_root = Path(__file__).parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
