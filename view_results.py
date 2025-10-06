#!/usr/bin/env python3
"""View full results matrix from checkpoint directory.

Usage:
  python view_results.py /path/to/checkpoint_dir
"""

import sys
import os

# Add the parent directory to path so we can import android_world modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from android_world import checkpointer as checkpointer_lib
from android_world import suite_utils


def view_results(checkpoint_dir: str):
    """Load and display full results from checkpoint directory.

    Args:
        checkpoint_dir: Path to the checkpoint directory containing .pkl.gz files
    """
    if not os.path.exists(checkpoint_dir):
        print(f"Error: Directory '{checkpoint_dir}' does not exist.")
        sys.exit(1)

    # Check if there are any checkpoint files
    pkl_files = [f for f in os.listdir(checkpoint_dir) if f.endswith('.pkl.gz')]
    if not pkl_files:
        print(f"Error: No checkpoint files (.pkl.gz) found in '{checkpoint_dir}'")
        sys.exit(1)

    print(f"Loading results from: {checkpoint_dir}")
    print(f"Found {len(pkl_files)} checkpoint files\n")

    # Load all episodes from checkpoint
    checkpointer = checkpointer_lib.IncrementalCheckpointer(checkpoint_dir)
    episodes = checkpointer.load()

    if not episodes:
        print("No episodes found in checkpoint files.")
        sys.exit(1)

    print(f"Loaded {len(episodes)} total episodes\n")
    print("=" * 80)
    print("FULL RESULTS MATRIX")
    print("=" * 80)

    # Process and display results
    result_df = suite_utils.process_episodes(episodes, print_summary=True)

    return result_df


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python view_results.py /path/to/checkpoint_dir")
        print("\nExample:")
        print("  python view_results.py ~/android_world/runs/run_20250928T170746099992")
        sys.exit(1)

    checkpoint_dir = sys.argv[1]

    # Expand user home directory if needed
    checkpoint_dir = os.path.expanduser(checkpoint_dir)

    result_df = view_results(checkpoint_dir)

    print("\n" + "=" * 80)
    print("Results loaded successfully!")
    print(f"Total tasks: {len(result_df)}")
    print(f"Overall success rate: {result_df['mean_success_rate'].mean():.2%}")
