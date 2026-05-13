from __future__ import annotations

import pytest

from packages.kb.agents.knowledge_base import KnowledgeBase, SearchResult
from packages.kb.agents.profiles import PROFILES, AgentProfile, get_profile

VALID_SOURCE_TYPES = {
    "nasa_payload_guide",
    "casis_solicitation",
    "iss_annual_report",
    "paper",
    "hardware_spec",
    "regulatory",
}


def test_all_profiles_have_config() -> None:
    """Every AgentProfile must have a corresponding ProfileConfig."""
    for profile in AgentProfile:
        config = get_profile(profile)
        assert config.profile == profile
        assert len(config.source_types) > 0
        assert config.default_k > 0
        assert config.default_top_n > 0


def test_profile_source_types_are_known() -> None:
    """Source types in profiles must match the schema's allowed values."""
    for config in PROFILES.values():
        for st in config.source_types:
            assert st in VALID_SOURCE_TYPES, f"Unknown source type: {st}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_kb_search_unscoped() -> None:
    """Unscoped KB searches the full corpus."""
    kb = KnowledgeBase()
    result = await kb.search("microgravity")
    assert isinstance(result, SearchResult)
    assert result.profile is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_kb_search_profile_bound() -> None:
    """A profile-bound KB applies the profile's source-type filter."""
    kb = KnowledgeBase.for_agent(AgentProfile.MICROGRAVITY)
    result = await kb.search("crystal growth")
    assert result.profile == AgentProfile.MICROGRAVITY
    allowed = set(PROFILES[AgentProfile.MICROGRAVITY].source_types)
    for chunk in result.chunks:
        assert chunk.source_type in allowed


@pytest.mark.asyncio
@pytest.mark.integration
async def test_kb_formatted_context_has_citation_markers() -> None:
    """Formatted context must include [1] markers for LLM citation."""
    kb = KnowledgeBase()
    result = await kb.search("space biology")
    if result.chunks:
        assert "[1]" in result.formatted_context
        assert "Query:" in result.formatted_context


@pytest.mark.asyncio
@pytest.mark.integration
async def test_kb_search_result_truthiness() -> None:
    """A result with no chunks should be falsy."""
    kb = KnowledgeBase()
    result = await kb.search("anything", source_types=["regulatory"])
    if not result.chunks:
        assert not result
        assert len(result) == 0


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.slow
async def test_kb_search_many_runs_in_parallel() -> None:
    """search_many should return one result per query."""
    kb = KnowledgeBase()
    results = await kb.search_many(["microgravity", "protein", "crystals"])
    assert len(results) == 3
    for r in results:
        assert isinstance(r, SearchResult)
