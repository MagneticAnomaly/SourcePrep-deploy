"""
API tests for clara-server.

These tests use a mock model to test API functionality
without requiring actual model loading.
"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from clara_server.server import create_app
from clara_server.config import Settings


@pytest.fixture
def mock_settings():
    """Create test settings."""
    return Settings(
        model="test/model",
        subfolder="compression-16",
        port=8765,
        backend="cpu",
    )


@pytest.fixture
def mock_model():
    """Create a mock ClaraModel."""
    model = Mock()
    model.is_loaded.return_value = True
    model.compress.return_value = {
        "success": True,
        "answer": "Test answer",
        "original_tokens": 100,
        "compressed_tokens": 6,
        "compression_ratio": 16.0,
        "latency_ms": 100.0,
    }
    model.get_status.return_value = {
        "model": "test/model",
        "subfolder": "compression-16",
        "initialized": True,
        "backend": "cpu",
        "device": "cpu",
        "requests_served": 0,
        "errors": 0,
        "avg_latency_ms": 0,
    }
    return model


@pytest.fixture
def client(mock_settings, mock_model):
    """Create test client with mocked model."""
    with patch("clara_server.server.get_model", return_value=mock_model):
        with patch("clara_server.server.load_model", return_value=mock_model):
            app = create_app(mock_settings)
            with TestClient(app) as client:
                yield client


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_ok(self, client):
        """Test health check returns OK when model loaded."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_health_not_loaded(self, mock_settings):
        """Test health check returns 503 when model not loaded."""
        mock_model = Mock()
        mock_model.is_loaded.return_value = False
        
        with patch("clara_server.server.get_model", return_value=mock_model):
            with patch("clara_server.server.load_model", return_value=mock_model):
                app = create_app(mock_settings)
                with TestClient(app) as client:
                    response = client.get("/health")
                    assert response.status_code == 503


class TestStatusEndpoint:
    """Tests for /status endpoint."""
    
    def test_status_returns_model_info(self, client):
        """Test status returns model information."""
        response = client.get("/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["model"] == "test/model"
        assert data["subfolder"] == "compression-16"
        assert data["initialized"] is True
        assert "uptime_seconds" in data


class TestCompressEndpoint:
    """Tests for /compress endpoint."""
    
    def test_compress_success(self, client):
        """Test successful compression."""
        response = client.post("/compress", json={
            "memories": ["Test memory 1", "Test memory 2"],
            "query": "What is the test about?",
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["answer"] == "Test answer"
        assert data["compression_ratio"] == 16.0
    
    def test_compress_with_max_tokens(self, client):
        """Test compression with custom max_new_tokens."""
        response = client.post("/compress", json={
            "memories": ["Test memory"],
            "query": "Test query",
            "max_new_tokens": 256,
        })
        
        assert response.status_code == 200
    
    def test_compress_missing_memories(self, client):
        """Test validation error for missing memories."""
        response = client.post("/compress", json={
            "query": "Test query",
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_compress_missing_query(self, client):
        """Test validation error for missing query."""
        response = client.post("/compress", json={
            "memories": ["Test memory"],
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_compress_empty_memories(self, client):
        """Test validation error for empty memories list."""
        response = client.post("/compress", json={
            "memories": [],
            "query": "Test query",
        })
        
        assert response.status_code == 422  # Validation error


class TestAPIKeyAuth:
    """Tests for API key authentication."""
    
    def test_compress_requires_api_key(self):
        """Test that compress requires API key when configured."""
        settings = Settings(
            model="test/model",
            api_key="test-secret-key",
        )
        
        mock_model = Mock()
        mock_model.is_loaded.return_value = True
        
        with patch("clara_server.server.get_model", return_value=mock_model):
            with patch("clara_server.server.load_model", return_value=mock_model):
                app = create_app(settings)
                with TestClient(app) as client:
                    # Without API key
                    response = client.post("/compress", json={
                        "memories": ["Test"],
                        "query": "Test",
                    })
                    assert response.status_code == 401
                    
                    # With wrong API key
                    response = client.post(
                        "/compress",
                        json={"memories": ["Test"], "query": "Test"},
                        headers={"Authorization": "Bearer wrong-key"},
                    )
                    assert response.status_code == 403
                    
                    # With correct API key
                    mock_model.compress.return_value = {"success": True, "answer": "Test"}
                    response = client.post(
                        "/compress",
                        json={"memories": ["Test"], "query": "Test"},
                        headers={"Authorization": "Bearer test-secret-key"},
                    )
                    assert response.status_code == 200
