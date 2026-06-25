"""dev.fun Arena SDK — build, test, and submit Arena agents.

Platform layer (submit/pack/comps) is environment-agnostic; per-game logic lives
under an environment package (the first is `arena_sdk.poker`). Test the SAME
strategy.py you submit, run self-play offline, get bb/100.
"""
from .poker.engine import run_match, play_one_hand, build_table, OPPONENTS
from .poker.contract import load_strategy, normalize_action, clamp_to_range
from .poker.read import (hero, hole_cards, button_seat, is_button, to_call,
                         pot_odds, can)
from .pack import build_bundle, BundleError
from .submit import submit, poll

__all__ = ["run_match", "play_one_hand", "build_table", "OPPONENTS",
           "load_strategy", "normalize_action", "clamp_to_range",
           "hero", "hole_cards", "button_seat", "is_button", "to_call",
           "pot_odds", "can", "build_bundle", "BundleError", "submit", "poll"]
__version__ = "0.7.1"
