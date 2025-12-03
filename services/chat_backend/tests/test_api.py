"""
Тесты API endpoints.
"""
import pytest


class TestHealthCheck:
    """Тесты health check."""
    
    def test_health_returns_200(self, test_client):
        """Health endpoint возвращает 200."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestChatAPI:
    """Тесты Chat API."""
    
    def test_hello_endpoint(self, test_client):
        """Hello endpoint работает."""
        response = test_client.get("/api/chat/hello")
        assert response.status_code == 200
        assert "Hello" in response.json()["message"]
    
    def test_chat_returns_response(self, test_client):
        """Chat endpoint возвращает ответ."""
        response = test_client.post(
            "/api/chat/",
            json={"message": "Привет!"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "conversation_id" in data
        assert "Привет" in data["answer"]
