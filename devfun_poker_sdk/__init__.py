"""dev.fun Poker SDK — local replica of the Arena server submission mode.

Test the SAME strategy.py you submit, run self-play offline, get bb/100.
"""
from .engine import run_match, play_one_hand, build_table, OPPONENTS
from .contract import load_strategy, normalize_action, clamp_to_range
from .pack import build_bundle, BundleError
from .submit import submit, poll

__all__ = ["run_match", "play_one_hand", "build_table", "OPPONENTS",
           "load_strategy", "normalize_action", "clamp_to_range",
           "build_bundle", "BundleError", "submit", "poll"]
__version__ = "0.2.3"
