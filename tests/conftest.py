# tests/conftest.py
import sys
from pathlib import Path

# Add project root to sys.path so test files can import from llm/, core/, etc.
sys.path.insert(0, str(Path(__file__).parent.parent))