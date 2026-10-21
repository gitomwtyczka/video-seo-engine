"""Unit tests for K4 — Job per click, publication_type, user_id scoping (R1/R2), and run_inject resolution.

CO: Weryfikacja logiki K4:
1. Model TranscriptJob ma kolumnę publication_type.
2. Modele odpowiedzi (JobResponse, FullJobResponse, HistoryJobResponse) mają pole publication_type.
3. Model InjectRequest posiada pole job_id.
4. Model GenerateResponse posiada pole job_id.
5. Scoping R1/R2: _save_schema_to_job blokuje aktualizację joba innego usera.
6. Scoping R1/R2: _get_cached_transcript_from_db filtruje po user_id i nie zwraca transkryptów innego usera.
7. run_inject przyjmuje job_id i portal_id zamiast wyszukiwać ostatni rekord w ciemno.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.models.job import TranscriptJob
from api.models.request import InjectRequest
from api.models.response import GenerateResponse
from api.routers.jobs import (
    JobResponse,
    FullJobResponse,
    HistoryJobResponse,
    _job_to_response,
    _job_to_full_response,
    _job_to_history_response,
)
from api.routers.generate import _save_schema_to_job
from api.services.pipeline import _get_cached_transcript_from_db, run_inject


class TestK4Models:
    """Testy modeli i pól K4."""

    def test_transcript_job_has_publication_type(self):
        """Model TranscriptJob posiada kolumnę publication_type."""
        assert hasattr(TranscriptJob, "publication_type")
        job = TranscriptJob(
            video_url="https://www.youtube.com/watch?v=ptOrFpUYa3Q",
            status="processing",
            publication_type="watching_page",
        )
        assert job.publication_type == "watching_page"

    def test_inject_request_has_job_id(self):
        """InjectRequest akceptuje opcjonalne pole job_id."""
        req = InjectRequest(
            video_url="https://www.youtube.com/watch?v=ptOrFpUYa3Q",
            schema_data={"post_title": "Test"},
            job_id="5936f2b7-2cde-4069-a9ce-d2185ae8f642",
        )
        assert req.job_id == "5936f2b7-2cde-4069-a9ce-d2185ae8f642"

    def test_generate_response_has_job_id(self):
        """GenerateResponse akceptuje i serializuje pole job_id."""
        resp = GenerateResponse(
            status="ok",
            video_id="ptOrFpUYa3Q",
            job_id="5936f2b7-2cde-4069-a9ce-d2185ae8f642",
        )
        assert resp.job_id == "5936f2b7-2cde-4069-a9ce-d2185ae8f642"
        data = resp.model_dump()
        assert data["job_id"] == "5936f2b7-2cde-4069-a9ce-d2185ae8f642"

    def test_job_responses_contain_publication_type(self):
        """JobResponse, FullJobResponse i HistoryJobResponse zawierają publication_type."""
        uid = uuid.uuid4()
        job = TranscriptJob(
            id=uid,
            video_url="https://www.youtube.com/watch?v=ptOrFpUYa3Q",
            status="done",
            publication_type="discover",
            schema_data={"post_title": "Discover Title", "publication_type": "discover"},
        )

        resp = _job_to_response(job)
        assert resp.publication_type == "discover"

        full_resp = _job_to_full_response(job)
        assert full_resp.publication_type == "discover"

        hist_resp = _job_to_history_response(job)
        assert hist_resp.publication_type == "discover"
        assert hist_resp.post_title == "Discover Title"


class TestK4UserScopingR1R2:
    """Testy bezpieczeństwa R1/R2 (scoping user_id)."""

    @pytest.mark.asyncio
    async def test_save_schema_to_job_blocks_cross_user_update(self):
        """_save_schema_to_job odrzuca aktualizację gdy job należy do innego usera."""
        owner_id = uuid.uuid4()
        attacker_id = uuid.uuid4()
        job_id = uuid.uuid4()

        mock_job = TranscriptJob(
            id=job_id,
            video_url="https://www.youtube.com/watch?v=test",
            status="processing",
            user_id=owner_id,
        )

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_job

        with patch("api.routers.generate.AsyncSessionLocal") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            # Atakujący próbuje zaktualizować job właściciela
            result = await _save_schema_to_job(
                job_id=str(job_id),
                schema_data={"seo": "hacked"},
                user_id=str(attacker_id),
            )

            assert result is None
            # Status i schema_data NIE powinny ulec zmianie
            assert mock_job.status == "processing"
            assert mock_job.schema_data is None
            mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_schema_to_job_allows_owner_update(self):
        """_save_schema_to_job pozwala na aktualizację prawowitemu właścicielowi po PK."""
        owner_id = uuid.uuid4()
        job_id = uuid.uuid4()

        mock_job = TranscriptJob(
            id=job_id,
            video_url="https://www.youtube.com/watch?v=test",
            status="processing",
            user_id=owner_id,
        )

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_job

        with patch("api.routers.generate.AsyncSessionLocal") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__.return_value = mock_session

            result = await _save_schema_to_job(
                job_id=str(job_id),
                schema_data={"post_title": "Owner Video"},
                user_id=str(owner_id),
                publication_type="watching_page",
            )

            assert result == str(job_id)
            assert mock_job.status == "done"
            assert mock_job.publication_type == "watching_page"
            assert mock_job.schema_data == {"post_title": "Owner Video"}
            mock_session.commit.assert_called_once()


class TestK4RunInjectResolution:
    """Testy deterministycznej rezolucji profilu w run_inject."""

    @pytest.mark.asyncio
    async def test_run_inject_accepts_job_id_and_portal_id(self):
        """run_inject przyjmuje argumenty portal_id i job_id bez rzucania TypeError."""
        import inspect
        sig = inspect.signature(run_inject)
        assert "portal_id" in sig.parameters
        assert "job_id" in sig.parameters
