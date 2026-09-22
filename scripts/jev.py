#!/usr/bin/env python3
"""Run the skill's pinned runtime without depending on the user's working directory."""
import os
import sys
from pathlib import Path

runtime = Path(__file__).resolve().parent / 'runtime'
os.chdir(runtime)
os.execvp('uv', ['uv', 'run', '--project', str(runtime), '--no-dev', 'python', '-m', 'jev_ultrafast.cli', *sys.argv[1:]])
