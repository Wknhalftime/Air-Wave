"""Tests for the backfill_artist_display_names script."""

from unittest.mock import AsyncMock, patch

import pytest

from airwave.core.models import Artist


def _fake_session_cm(session):
    """Return an async context manager that yields the given session."""

    class _FakeCM:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            pass

    return _FakeCM()


@pytest.fixture
def patch_db_session(db_session):
    """Patch AsyncSessionLocal to use test db_session."""
    import airwave.scripts.backfill_artist_display_names as backfill_mod
    with patch.object(
        backfill_mod,
        "AsyncSessionLocal",
        return_value=_fake_session_cm(db_session),
    ):
        yield db_session


@pytest.mark.asyncio
class TestBackfillArtistDisplayNames:
    """Tests for backfill_artist_display_names script behavior."""

    async def test_dry_run_does_not_modify_database(self, patch_db_session):
        """--dry-run should not call update_artist_display_names_from_musicbrainz."""
        # Create artist with MBID
        artist = Artist(
            name="metallica",
            musicbrainz_id="65f4f0c5-ef9e-490c-aee3-909e7ae6b2ab",
            display_name=None,
        )
        patch_db_session.add(artist)
        await patch_db_session.flush()

        with patch(
            "airwave.scripts.backfill_artist_display_names.FileScanner"
        ) as MockScanner:
            mock_scanner = AsyncMock()
            MockScanner.return_value = mock_scanner

            from airwave.scripts.backfill_artist_display_names import backfill_artists_with_mbids

            await backfill_artists_with_mbids(
                batch_size=50, limit=10, dry_run=True
            )

        # Scanner's update method should NOT be called in dry run
        mock_scanner.update_artist_display_names_from_musicbrainz.assert_not_called()

        # Database unchanged
        await patch_db_session.refresh(artist)
        assert artist.display_name is None

    async def test_skip_mbid_only_updates_artists_without_mbids(self, patch_db_session):
        """--skip-mbid skips MusicBrainz fetch and only runs non-MBID backfill."""
        # Artist WITH MBID - should not be touched when skip_mbid
        artist_with_mbid = Artist(
            name="metallica",
            musicbrainz_id="65f4f0c5-ef9e-490c-aee3-909e7ae6b2ab",
            display_name=None,
        )
        # Artist WITHOUT MBID - should get display_name = name
        artist_without_mbid = Artist(
            name="local_band",
            musicbrainz_id=None,
            display_name=None,
        )
        patch_db_session.add(artist_with_mbid)
        patch_db_session.add(artist_without_mbid)
        await patch_db_session.flush()

        # Run only the non-MBID step (simulates --skip-mbid)
        from airwave.scripts.backfill_artist_display_names import backfill_artists_without_mbids

        await backfill_artists_without_mbids()

        await patch_db_session.refresh(artist_with_mbid)
        await patch_db_session.refresh(artist_without_mbid)

        # Artist with MBID unchanged (we skipped that step)
        assert artist_with_mbid.display_name is None
        # Artist without MBID gets display_name = name
        assert artist_without_mbid.display_name == "local_band"

    async def test_backfill_artists_without_mbids_sets_display_name(self, patch_db_session):
        """backfill_artists_without_mbids sets display_name = name for artists without MBID."""
        artist = Artist(name="unknown_artist", musicbrainz_id=None, display_name=None)
        patch_db_session.add(artist)
        await patch_db_session.flush()

        from airwave.scripts.backfill_artist_display_names import backfill_artists_without_mbids

        await backfill_artists_without_mbids()

        await patch_db_session.refresh(artist)
        assert artist.display_name == "unknown_artist"

    async def test_main_with_skip_mbid_skips_musicbrainz_step(self, patch_db_session):
        """main() with --skip-mbid does not call MusicBrainz-backed backfill."""
        artist = Artist(name="local", musicbrainz_id=None, display_name=None)
        patch_db_session.add(artist)
        await patch_db_session.flush()

        with patch(
            "airwave.scripts.backfill_artist_display_names.backfill_artists_with_mbids",
            new_callable=AsyncMock,
        ) as mock_mbids:
            with patch(
                "airwave.scripts.backfill_artist_display_names.backfill_artists_without_mbids",
                new_callable=AsyncMock,
            ) as mock_no_mbids:
                with patch("sys.argv", ["backfill", "--skip-mbid"]):
                    from airwave.scripts.backfill_artist_display_names import main

                    await main()

        # With --skip-mbid, MBID backfill is NOT called
        mock_mbids.assert_not_called()
        # Non-MBID backfill IS called (unless dry-run, which we didn't pass)
        mock_no_mbids.assert_called_once()
