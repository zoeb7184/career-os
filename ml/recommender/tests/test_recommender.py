"""
ml/recommender/tests/test_recommender.py
Tests for the recommender node.
"""
import pytest
from unittest.mock import patch, MagicMock
from ml.recommender.recommender import JobRecommender, RecommenderError


def _mock_qdrant_hits(n: int = 15):
    """Create mock Qdrant search results."""
    hits = []
    for i in range(n):
        hit = MagicMock()
        hit.score = 0.9 - i * 0.02
        hit.id    = f"qdrant-id-{i}"
        hit.payload = {
            "job_id":     f"job-{i}",
            "title":      f"Data Scientist Level {i}",
            "company":    f"Company {i}",
            "location":   "Berlin",
            "country":    "DE",
            "remote_type": "hybrid",
            "salary_min": 60000 + i * 1000,
            "salary_max": 90000 + i * 1000,
            "posted_at":  "2024-06-01T00:00:00",
            "url":        f"https://example.com/job-{i}",
            "skills":     ["Python", "SQL", "TensorFlow"],
        }
        hits.append(hit)
    return hits


def test_recommender_returns_top_n():
    """Should return exactly top_n results."""
    rec = JobRecommender()
    mock_hits = _mock_qdrant_hits(20)

    with (
        patch.object(rec._embedder, "embed_chunks", return_value=[[0.1] * 384]),
        patch("ml.recommender.recommender.QdrantClient") as MockClient,
    ):
        MockClient.return_value.search.return_value = mock_hits
        result = rec.recommend(
            resume_text = "Data scientist with Python and SQL experience",
            user_skills = ["Python", "SQL"],
            user_id     = "user-123",
            top_n       = 5,
        )

    assert len(result.recommendations) == 5


def test_recommender_sorted_by_final_score():
    """Recommendations must be sorted highest score first."""
    rec = JobRecommender()
    mock_hits = _mock_qdrant_hits(15)

    with (
        patch.object(rec._embedder, "embed_chunks", return_value=[[0.1] * 384]),
        patch("ml.recommender.recommender.QdrantClient") as MockClient,
    ):
        MockClient.return_value.search.return_value = mock_hits
        result = rec.recommend(
            resume_text = "Data scientist resume text",
            user_skills = ["Python"],
            user_id     = "user-123",
        )

    scores = [r.final_score for r in result.recommendations]
    assert scores == sorted(scores, reverse=True), "Results not sorted by score"


def test_recommender_insufficient_jobs_raises_rec003():
    """REC_003: should raise when fewer than 10 jobs in Qdrant."""
    rec = JobRecommender()

    with (
        patch.object(rec._embedder, "embed_chunks", return_value=[[0.1] * 384]),
        patch("ml.recommender.recommender.QdrantClient") as MockClient,
    ):
        MockClient.return_value.search.return_value = _mock_qdrant_hits(5)  # Only 5 hits
        with pytest.raises(RecommenderError) as exc_info:
            rec.recommend(resume_text="resume", user_skills=[], user_id="u1")
        assert exc_info.value.code == "REC_003"


def test_matched_skills_populated():
    """matched_skills should include overlap between user and job skills."""
    rec = JobRecommender()
    mock_hits = _mock_qdrant_hits(15)

    with (
        patch.object(rec._embedder, "embed_chunks", return_value=[[0.1] * 384]),
        patch("ml.recommender.recommender.QdrantClient") as MockClient,
    ):
        MockClient.return_value.search.return_value = mock_hits
        result = rec.recommend(
            resume_text = "Python and SQL developer",
            user_skills = ["Python", "SQL", "TensorFlow"],
            user_id     = "user-123",
        )

    # Every job in mock_hits has ["Python", "SQL", "TensorFlow"]
    first = result.recommendations[0]
    assert "Python" in first.matched_skills
