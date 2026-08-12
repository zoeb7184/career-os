"""
data-pipeline/tests/test_skill_normalizer.py
Tests for the skill normalizer node.
"""
import pytest
from data_pipeline.transformers.skill_normalizer import normalise_skill, normalise_skills


def test_exact_canonical_match():
    assert normalise_skill("Python") == "Python"

def test_lowercase_alias():
    assert normalise_skill("python3") == "Python"
    assert normalise_skill("py") == "Python"

def test_uppercase_alias():
    assert normalise_skill("TENSORFLOW") == "TensorFlow"

def test_framework_alias():
    assert normalise_skill("sklearn") == "scikit-learn"
    assert normalise_skill("pytorch") == "PyTorch"

def test_unknown_skill_returns_none():
    assert normalise_skill("competitive-knitting-2024") is None

def test_empty_string_returns_none():
    assert normalise_skill("") is None
    assert normalise_skill("   ") is None

def test_batch_normalisation():
    result = normalise_skills(["python3", "TENSORFLOW", "sklearn", "juggling"])
    assert result["python3"] == "Python"
    assert result["TENSORFLOW"] == "TensorFlow"
    assert result["sklearn"] == "scikit-learn"
    assert result["juggling"] is None

def test_cloud_aliases():
    assert normalise_skill("amazon web services") == "AWS"
    assert normalise_skill("google cloud platform") == "GCP"

def test_database_aliases():
    assert normalise_skill("postgres") == "PostgreSQL"
    assert normalise_skill("mongo") == "MongoDB"
