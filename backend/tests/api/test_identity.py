import pytest
from airwave.core.models import ArtistAlias, ProposedSplit
from httpx import AsyncClient
from sqlalchemy import select


@pytest.mark.asyncio
async def test_get_pending_splits(client: AsyncClient, db_session):
    # Add a pending split
    split = ProposedSplit(
        raw_artist="Ozzy/Primus",
        proposed_artists=["Ozzy", "Primus"],
        status="PENDING",
        confidence=0.9,
    )
    db_session.add(split)
    await db_session.commit()

    response = await client.get("/api/v1/identity/splits/pending")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["raw_artist"] == "Ozzy/Primus"


@pytest.mark.asyncio
async def test_confirm_split_api(client: AsyncClient, db_session):
    # Add a pending split
    split = ProposedSplit(
        raw_artist="Nirvana/In Utero",
        proposed_artists=["Nirvana", "In Utero"],
        status="PENDING",
        confidence=0.9,
    )
    db_session.add(split)
    await db_session.commit()

    response = await client.post(f"/api/v1/identity/splits/{split.id}/confirm")
    assert response.status_code == 200
    assert response.json()["resolved_as"] == "Nirvana & In Utero"

    # Verify DB state
    await db_session.refresh(split)
    assert split.status == "APPROVED"

    # Verify Alias Map entry
    stmt = select(ArtistAlias).where(ArtistAlias.raw_name == "Nirvana/In Utero")
    res = await db_session.execute(stmt)
    alias = res.scalar_one_or_none()
    assert alias is not None
    assert alias.resolved_name == "Nirvana & In Utero"
    assert alias.is_verified is True


@pytest.mark.asyncio
async def test_reject_split_api(client: AsyncClient, db_session):
    # Add a pending split
    split = ProposedSplit(
        raw_artist="Hall & Oates",
        proposed_artists=["Hall", "Oates"],
        status="PENDING",
        confidence=0.9,
    )
    db_session.add(split)
    await db_session.commit()

    response = await client.post(f"/api/v1/identity/splits/{split.id}/reject")
    assert response.status_code == 200

    # Verify DB state
    await db_session.refresh(split)
    assert split.status == "REJECTED"

    # Verify Alias Map entry (Negative Cache: raw -> raw)
    stmt = select(ArtistAlias).where(ArtistAlias.raw_name == "Hall & Oates")
    res = await db_session.execute(stmt)
    alias = res.scalar_one_or_none()
    assert alias is not None
    assert alias.resolved_name == "Hall & Oates"
    assert alias.is_verified is True
