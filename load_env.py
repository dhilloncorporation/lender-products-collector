#!/usr/bin/env python3
"""
Simple .env file loader - just like your other projects.
"""

import os
import sys
from pathlib import Path

def load_env():
    """Load .env file if it exists."""
    # Set UTF-8 encoding for Windows console
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except:
            pass
    
    env_file = Path(".env")
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Clean the value of any null characters
                        value = value.replace('\x00', '').strip()
                        if value:
                            os.environ[key] = value
            print("Loaded .env file")
        except Exception as e:
            print(f"Error loading .env file: {e}")
    else:
        print(".env file not found - create it with: OPENAI_API_KEY=your_key")

# Auto-load when imported
load_env()
