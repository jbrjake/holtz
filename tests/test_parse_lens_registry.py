"""Tests for lens registry parser."""
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "holtz" / "scripts"))

from parse_lens_registry import parse_lens_registry  # noqa: E402, I001


MINIMAL_REGISTRY = textwrap.dedent("""\
    # Lens Registry

    Some header text.

    ## component
    **Focus:** Individual functions, classes, modules in isolation
    **Scope:** per-file
    **Audit priorities:** Correctness, edge cases
    **Failure modes:** Logic errors
    **Entry point:** Standard Steps 6-8

    ## integration
    **Focus:** Contracts and assumptions between modules
    **Scope:** cross-file
    **Audit priorities:** Interface agreements, shared state
    **Failure modes:** Modules that disagree
    **Entry point:** Query impact graph for edges
""")


def test_parse_returns_list():
    """Parser returns a list of lens dicts."""
    result = parse_lens_registry(MINIMAL_REGISTRY)
    assert isinstance(result, list)
    assert len(result) == 2


def test_parse_extracts_name():
    """Each lens has its heading as the name."""
    result = parse_lens_registry(MINIMAL_REGISTRY)
    names = [lens["name"] for lens in result]
    assert "component" in names
    assert "integration" in names


def test_parse_extracts_scope():
    """Scope field is parsed correctly."""
    result = parse_lens_registry(MINIMAL_REGISTRY)
    by_name = {lens["name"]: lens for lens in result}
    assert by_name["component"]["scope"] == "per-file"
    assert by_name["integration"]["scope"] == "cross-file"


def test_parse_extracts_all_fields():
    """All five fields are present in parsed output."""
    result = parse_lens_registry(MINIMAL_REGISTRY)
    for lens in result:
        assert "name" in lens
        assert "focus" in lens
        assert "scope" in lens
        assert "audit_priorities" in lens
        assert "failure_modes" in lens
        assert "entry_point" in lens


def test_parse_multiline_field():
    """Fields that span multiple lines are joined."""
    registry = textwrap.dedent("""\
        ## data-flow
        **Focus:** How data transforms as it moves through the system
        **Scope:** cross-file
        **Audit priorities:** Serialization/deserialization boundaries, type coercion,
        lossy transformations, format assumptions
        **Failure modes:** Data corruption at boundaries
        **Entry point:** Follow data from ingestion to output
    """)
    result = parse_lens_registry(registry)
    assert len(result) == 1
    assert "lossy transformations" in result[0]["audit_priorities"]


def test_parse_scope_invalid_raises():
    """Invalid scope value raises ValueError."""
    import pytest
    registry = textwrap.dedent("""\
        ## bad-lens
        **Focus:** Something
        **Scope:** hybrid
        **Audit priorities:** Things
        **Failure modes:** Stuff
        **Entry point:** Somewhere
    """)
    with pytest.raises(ValueError, match="scope"):
        parse_lens_registry(registry)


def test_parse_missing_scope_raises():
    """Missing scope field raises ValueError."""
    import pytest
    registry = textwrap.dedent("""\
        ## old-lens
        **Focus:** Something
        **Audit priorities:** Things
        **Failure modes:** Stuff
        **Entry point:** Somewhere
    """)
    with pytest.raises(ValueError, match="[Ss]cope"):
        parse_lens_registry(registry)


def test_parse_live_registry():
    """Live lens-registry.md parses without errors and has 13 lenses."""
    registry_path = REPO_ROOT / "skills" / "holtz" / "references" / "lens-registry.md"
    if not registry_path.exists():
        import pytest
        pytest.skip("No live lens-registry.md")
    text = registry_path.read_text()
    result = parse_lens_registry(text)
    assert len(result) == 13
    scopes = {lens["scope"] for lens in result}
    assert scopes == {"per-file", "cross-file"}


def test_filter_by_scope():
    """Helper function filters lenses by scope."""
    from parse_lens_registry import filter_by_scope
    result = parse_lens_registry(MINIMAL_REGISTRY)
    per_file = filter_by_scope(result, "per-file")
    cross_file = filter_by_scope(result, "cross-file")
    assert len(per_file) == 1
    assert per_file[0]["name"] == "component"
    assert len(cross_file) == 1
    assert cross_file[0]["name"] == "integration"
