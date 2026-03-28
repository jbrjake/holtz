"""Model pricing tables and dollar cost computation.

Provides longest-prefix model matching so version-suffixed model names
(e.g. ``"claude-opus-4-6-20251101"``) resolve to their base pricing entry.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

from token_profiler.models import DollarCost, Usage

# ---------------------------------------------------------------------------
# Pricing table  (dollars per token)
# ---------------------------------------------------------------------------

PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {
        "input": 15.00 / 1_000_000,
        "cache_creation": 18.75 / 1_000_000,  # 1.25x input
        "cache_read": 1.50 / 1_000_000,  # 0.1x input
        "output": 75.00 / 1_000_000,  # 5x input
    },
    "claude-sonnet-4-6": {
        "input": 3.00 / 1_000_000,
        "cache_creation": 3.75 / 1_000_000,
        "cache_read": 0.30 / 1_000_000,
        "output": 15.00 / 1_000_000,
    },
    "claude-haiku-4-5": {
        "input": 0.80 / 1_000_000,
        "cache_creation": 1.00 / 1_000_000,
        "cache_read": 0.08 / 1_000_000,
        "output": 4.00 / 1_000_000,
    },
    "unknown": {
        "input": 0.0,
        "cache_creation": 0.0,
        "cache_read": 0.0,
        "output": 0.0,
    },
}


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def get_pricing(model: str) -> dict[str, float]:
    """Look up pricing for *model* using longest-prefix matching.

    ``"claude-opus-4-6-20251101"`` matches the ``"claude-opus-4-6"`` key.
    Falls back to the ``"unknown"`` key (zero pricing) with a warning to
    stderr if no prefix matches.
    """
    # Exact match — fast path (including "unknown" sentinel)
    if model in PRICING:
        return PRICING[model]

    # Longest-prefix match among non-"unknown" keys
    best_key: str | None = None
    best_len = 0
    for key in PRICING:
        if key == "unknown":
            continue
        if model.startswith(key) and len(key) > best_len:
            best_key = key
            best_len = len(key)

    if best_key is not None:
        return PRICING[best_key]

    # Fallback
    print(
        f"warning: no pricing entry for model {model!r}, using zero rates",
        file=sys.stderr,
    )
    return PRICING["unknown"]


# ---------------------------------------------------------------------------
# Cost computation
# ---------------------------------------------------------------------------


def apply_pricing_to_usage(usage: Usage, model: str) -> DollarCost:
    """Compute dollar costs from a :class:`Usage` object and model name."""
    rates = get_pricing(model)
    return DollarCost(
        input_cost=usage.input_tokens * rates["input"],
        cache_creation_cost=usage.cache_creation_input_tokens * rates["cache_creation"],
        cache_read_cost=usage.cache_read_input_tokens * rates["cache_read"],
        output_cost=usage.output_tokens * rates["output"],
    )


def make_pricing_fn(
    custom_table: dict[str, dict[str, float]] | None,
) -> Callable[[Usage, str], DollarCost]:
    """Return a pricing function, optionally using a custom pricing table.

    If *custom_table* is ``None``, returns :func:`apply_pricing_to_usage`
    (the default pricing function).  Otherwise, returns a function that
    looks up rates in *custom_table* first, falling back to the built-in
    ``PRICING`` table for models not present in the override.
    """
    if custom_table is None:
        return apply_pricing_to_usage

    merged = dict(PRICING)
    merged.update(custom_table)

    def _custom_pricing(usage: Usage, model: str) -> DollarCost:
        # Exact match in merged table
        if model in merged:
            rates = merged[model]
        else:
            # Longest-prefix match (same logic as get_pricing)
            best_key: str | None = None
            best_len = 0
            for key in merged:
                if key == "unknown":
                    continue
                if model.startswith(key) and len(key) > best_len:
                    best_key = key
                    best_len = len(key)
            rates = merged[best_key] if best_key is not None else merged.get("unknown", PRICING["unknown"])

        return DollarCost(
            input_cost=usage.input_tokens * rates["input"],
            cache_creation_cost=usage.cache_creation_input_tokens * rates["cache_creation"],
            cache_read_cost=usage.cache_read_input_tokens * rates["cache_read"],
            output_cost=usage.output_tokens * rates["output"],
        )

    return _custom_pricing
