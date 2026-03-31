"""Tests for token_profiler pricing module."""

from token_profiler.models import DollarCost, Usage
from token_profiler.pricing import PRICING, apply_pricing_to_usage, get_pricing, make_pricing_fn

# ---------------------------------------------------------------------------
# PRICING table — verify spec values
# ---------------------------------------------------------------------------


class TestPricingTable:
    def test_opus_input_rate(self):
        assert PRICING["claude-opus-4-6"]["input"] == 15.00 / 1_000_000

    def test_opus_cache_creation_rate(self):
        """cache_creation = 1.25x input."""
        assert PRICING["claude-opus-4-6"]["cache_creation"] == 18.75 / 1_000_000

    def test_opus_cache_read_rate(self):
        """cache_read = 0.1x input."""
        assert PRICING["claude-opus-4-6"]["cache_read"] == 1.50 / 1_000_000

    def test_opus_output_rate(self):
        """output = 5x input."""
        assert PRICING["claude-opus-4-6"]["output"] == 75.00 / 1_000_000

    def test_sonnet_rates(self):
        s = PRICING["claude-sonnet-4-6"]
        assert s["input"] == 3.00 / 1_000_000
        assert s["cache_creation"] == 3.75 / 1_000_000
        assert s["cache_read"] == 0.30 / 1_000_000
        assert s["output"] == 15.00 / 1_000_000

    def test_haiku_rates(self):
        h = PRICING["claude-haiku-4-5"]
        assert h["input"] == 0.80 / 1_000_000
        assert h["cache_creation"] == 1.00 / 1_000_000
        assert h["cache_read"] == 0.08 / 1_000_000
        assert h["output"] == 4.00 / 1_000_000

    def test_unknown_rates_all_zero(self):
        u = PRICING["unknown"]
        assert u["input"] == 0.0
        assert u["cache_creation"] == 0.0
        assert u["cache_read"] == 0.0
        assert u["output"] == 0.0

    def test_pricing_keys(self):
        """Each entry must have exactly the four expected keys."""
        expected_keys = {"input", "cache_creation", "cache_read", "output"}
        for model, rates in PRICING.items():
            assert set(rates.keys()) == expected_keys, f"{model} has wrong keys"


# ---------------------------------------------------------------------------
# get_pricing — exact match, prefix match, unknown fallback
# ---------------------------------------------------------------------------


class TestGetPricing:
    def test_exact_match(self):
        result = get_pricing("claude-opus-4-6")
        assert result == PRICING["claude-opus-4-6"]

    def test_prefix_match_version_suffix(self):
        """A version-suffixed model name should match its prefix."""
        result = get_pricing("claude-opus-4-6-20251101")
        assert result == PRICING["claude-opus-4-6"]

    def test_prefix_match_sonnet(self):
        result = get_pricing("claude-sonnet-4-6-20250101")
        assert result == PRICING["claude-sonnet-4-6"]

    def test_prefix_match_haiku(self):
        result = get_pricing("claude-haiku-4-5-20250301")
        assert result == PRICING["claude-haiku-4-5"]

    def test_longest_prefix_wins(self):
        """If multiple prefixes match, the longest one should win."""
        # "claude-opus-4-6" is longer than "claude-opus" (if it existed),
        # so the correct entry should be selected.
        result = get_pricing("claude-opus-4-6-extra-stuff")
        assert result == PRICING["claude-opus-4-6"]

    def test_unknown_model_returns_zero_pricing(self):
        result = get_pricing("totally-unknown-model")
        assert result == PRICING["unknown"]

    def test_unknown_model_warns_to_stderr(self, capsys):
        get_pricing("totally-unknown-model")
        captured = capsys.readouterr()
        assert "totally-unknown-model" in captured.err
        assert captured.out == ""  # nothing on stdout

    def test_returns_dict_with_correct_keys(self):
        result = get_pricing("claude-opus-4-6")
        assert set(result.keys()) == {"input", "cache_creation", "cache_read", "output"}


# ---------------------------------------------------------------------------
# apply_pricing_to_usage
# ---------------------------------------------------------------------------


class TestApplyPricingToUsage:
    def test_basic_computation(self):
        usage = Usage(
            input_tokens=1000,
            cache_creation_input_tokens=500,
            cache_read_input_tokens=2000,
            output_tokens=300,
        )
        result = apply_pricing_to_usage(usage, "claude-opus-4-6")
        rates = PRICING["claude-opus-4-6"]

        assert abs(result.input_cost - 1000 * rates["input"]) < 1e-12
        assert abs(result.cache_creation_cost - 500 * rates["cache_creation"]) < 1e-12
        assert abs(result.cache_read_cost - 2000 * rates["cache_read"]) < 1e-12
        assert abs(result.output_cost - 300 * rates["output"]) < 1e-12

    def test_returns_dollar_cost_instance(self):
        usage = Usage(input_tokens=100, output_tokens=50)
        result = apply_pricing_to_usage(usage, "claude-opus-4-6")
        assert isinstance(result, DollarCost)

    def test_total_cost_is_sum_of_components(self):
        usage = Usage(
            input_tokens=10_000,
            cache_creation_input_tokens=5_000,
            cache_read_input_tokens=20_000,
            output_tokens=3_000,
        )
        result = apply_pricing_to_usage(usage, "claude-opus-4-6")
        expected_total = (
            result.input_cost
            + result.cache_creation_cost
            + result.cache_read_cost
            + result.output_cost
        )
        assert abs(result.total_cost - expected_total) < 1e-12

    def test_zero_usage_zero_cost(self):
        usage = Usage()
        result = apply_pricing_to_usage(usage, "claude-opus-4-6")
        assert result.total_cost == 0.0

    def test_unknown_model_zero_cost(self):
        usage = Usage(input_tokens=100_000, output_tokens=50_000)
        result = apply_pricing_to_usage(usage, "some-unknown-model")
        assert result.total_cost == 0.0

    def test_versioned_model_name(self):
        """apply_pricing_to_usage should work with version-suffixed model names."""
        usage = Usage(input_tokens=1_000_000, output_tokens=0)
        result = apply_pricing_to_usage(usage, "claude-opus-4-6-20251101")
        # 1M input tokens at $15/MTok = $15.00
        assert abs(result.input_cost - 15.00) < 1e-9

    def test_opus_million_token_costs(self):
        """Verify well-known Opus costs for 1M tokens of each type."""
        usage = Usage(
            input_tokens=1_000_000,
            cache_creation_input_tokens=1_000_000,
            cache_read_input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        result = apply_pricing_to_usage(usage, "claude-opus-4-6")
        assert abs(result.input_cost - 15.00) < 1e-9
        assert abs(result.cache_creation_cost - 18.75) < 1e-9
        assert abs(result.cache_read_cost - 1.50) < 1e-9
        assert abs(result.output_cost - 75.00) < 1e-9
        assert abs(result.total_cost - 110.25) < 1e-9


# ---------------------------------------------------------------------------
# make_pricing_fn — custom pricing override  (BH-011)
# ---------------------------------------------------------------------------


class TestMakePricingFn:
    """Custom pricing tables should override default rates."""

    def test_custom_rates_override_defaults(self):
        """Custom table overrides rates for a known model."""
        custom_table = {
            "claude-opus-4-6": {
                "input": 10.0 / 1_000_000,
                "cache_creation": 12.5 / 1_000_000,
                "cache_read": 1.0 / 1_000_000,
                "output": 50.0 / 1_000_000,
            },
        }
        fn = make_pricing_fn(custom_table)
        usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
        result = fn(usage, "claude-opus-4-6")
        assert abs(result.input_cost - 10.0) < 1e-9
        assert abs(result.output_cost - 50.0) < 1e-9

    def test_custom_table_falls_through_to_default(self):
        """Models not in custom table still use default pricing."""
        custom_table = {
            "claude-opus-4-6": {
                "input": 99.0 / 1_000_000,
                "cache_creation": 0.0,
                "cache_read": 0.0,
                "output": 0.0,
            },
        }
        fn = make_pricing_fn(custom_table)
        usage = Usage(input_tokens=1_000_000)
        result = fn(usage, "claude-sonnet-4-6")
        # Should use default sonnet pricing, not opus override
        assert abs(result.input_cost - 3.0) < 1e-9

    def test_none_table_returns_default_fn(self):
        """Passing None should return the default apply_pricing_to_usage."""
        fn = make_pricing_fn(None)
        usage = Usage(input_tokens=1_000_000)
        result = fn(usage, "claude-opus-4-6")
        assert abs(result.input_cost - 15.0) < 1e-9
