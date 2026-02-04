import pytest
from airwave.core.models import ArtistAlias, ProposedSplit
from airwave.worker.identity_resolver import IdentityResolver
from sqlalchemy import select


@pytest.mark.asyncio
async def test_detect_split():
    resolver = IdentityResolver(None)

    # Simple slash
    assert resolver._detect_split("Ozzy/Primus") == ["Ozzy", "Primus"]
    # With spaces
    assert resolver._detect_split("Ozzy / Primus") == ["Ozzy", "Primus"]
    # w/
    # "GnR" -> "Gnr" due to Title Casing rules in _clean_artist_name
    assert resolver._detect_split("GnR w/ Slash") == ["Gnr", "Slash"]
    # feat.
    assert resolver._detect_split("Eminem feat. Rihanna") == [
        "Eminem",
        "Rihanna",
    ]
    # and
    assert resolver._detect_split("Simon and Garfunkel") == [
        "Simon",
        "Garfunkel",
    ]
    # &
    assert resolver._detect_split("Hall & Oates") == ["Hall", "Oates"]

    # Exceptions
    assert resolver._detect_split("AC/DC") is None
    assert resolver._detect_split("P!nk") is None


@pytest.mark.asyncio
async def test_resolve_batch_caching(db_session):
    resolver = IdentityResolver(db_session)

    # 1. Add an alias
    alias = ArtistAlias(
        raw_name="GnR", resolved_name="Guns N' Roses", is_verified=True
    )
    db_session.add(alias)

    # 2. Add a negative cache
    neg_alias = ArtistAlias(raw_name="Unknown Artist", is_null=True)
    db_session.add(neg_alias)

    await db_session.commit()

    # Test batch resolution
    results = await resolver.resolve_batch(
        ["GnR", "Unknown Artist", "New Artist"]
    )

    assert results["GnR"] == "Guns N' Roses"
    assert (
        results["Unknown Artist"] == "Unknown Artist"
    )  # matches raw but handled via is_null
    assert results["New Artist"] == "New Artist"


@pytest.mark.asyncio
async def test_split_registration(db_session):
    resolver = IdentityResolver(db_session)

    # Batch resolve with a split
    results = await resolver.resolve_batch(["Ozzy/Primus"])
    await db_session.flush()

    # Verify split was registered
    stmt = select(ProposedSplit).where(
        ProposedSplit.raw_artist == "Ozzy/Primus"
    )
    res = await db_session.execute(stmt)
    proposal = res.scalar_one_or_none()

    assert proposal is not None
    assert proposal.proposed_artists == ["Ozzy", "Primus"]
    assert proposal.status == "PENDING"

    # Second call should not double-register (Batch optimization check)
    await resolver.resolve_batch(["Ozzy/Primus"])
    stmt_all = select(ProposedSplit).where(
        ProposedSplit.raw_artist == "Ozzy/Primus"
    )
    res_all = await db_session.execute(stmt_all)
    assert len(res_all.scalars().all()) == 1
