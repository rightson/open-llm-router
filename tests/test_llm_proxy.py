"""
Pytest tests for LLM Proxy API verification
Tests all backends defined in backends.json
"""

import pytest
import json
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Import the FastAPI app
import sys
sys.path.insert(0, '..')
from src.openwebui_service.llm_proxy import app

class TestLLMProxy:
    """Test suite for LLM Proxy functionality"""
    
    def setup_class(self):
        """Setup test class with backends configuration"""
        self.client = TestClient(app)
        
        # Load backends configuration
        with open('../conf/backends.json', 'r') as f:
            self.config = json.load(f)
        
        self.backends = self.config['backends']
    
    def test_health_endpoint(self):
        """Test the health check endpoint"""
        response = self.client.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    @pytest.mark.parametrize("backend_name", ["openai", "groq", "claude", "gemini"])
    def test_backend_configuration(self, backend_name):
        """Test that all backends are properly configured"""
        assert backend_name in self.backends
        backend = self.backends[backend_name]
        
        # Check required fields
        required_fields = ["name", "base_url", "api_key_env", "models"]
        for field in required_fields:
            assert field in backend, f"Backend {backend_name} missing {field}"
        
        # Check models structure
        assert isinstance(backend["models"], list)
        assert len(backend["models"]) > 0
    
    def test_openai_model_routing(self):
        """Test OpenAI model routing logic"""
        # Test GPT models
        test_cases = [
            "gpt-4",
            "gpt-3.5-turbo", 
            "gpt-4-turbo"
        ]
        
        for model in test_cases:
            # Import the routing function
            from src.openwebui_service.llm_proxy import choose_backend
            
            # Mock environment variable
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
                backend = choose_backend(model)
                assert "api.openai.com" in backend["base_url"]
                assert backend["api_key"] == "test-key"
    
    def test_groq_model_routing(self):
        """Test Groq model routing logic"""
        test_cases = [
            "llama-3.1-70b-versatile",
            "mixtral-8x7b-32768"
        ]
        
        for model in test_cases:
            from src.openwebui_service.llm_proxy import choose_backend
            
            with patch.dict(os.environ, {'GROQ_API_KEY': 'test-groq-key'}):
                backend = choose_backend(model)
                assert "api.groq.com" in backend["base_url"]
                assert backend["api_key"] == "test-groq-key"
    
    def test_claude_model_routing(self):
        """Test Claude model routing logic"""
        test_cases = [
            "claude-3-5-sonnet",
            "claude-3-haiku"
        ]
        
        for model in test_cases:
            from src.openwebui_service.llm_proxy import choose_backend
            
            with patch.dict(os.environ, {'CLAUDE_API_KEY': 'test-claude-key'}):
                backend = choose_backend(model)
                assert "localhost:9000" in backend["base_url"]
                assert backend["api_key"] == "test-claude-key"
    
    def test_gemini_model_routing(self):
        """Test Gemini model routing logic"""
        test_cases = [
            "gemini-pro",
            "gemini-pro-vision"
        ]
        
        for model in test_cases:
            from src.openwebui_service.llm_proxy import choose_backend
            
            with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-gemini-key'}):
                backend = choose_backend(model)
                assert "localhost:9001" in backend["base_url"]
                assert backend["api_key"] == "test-gemini-key"
    
    def test_unknown_model_error(self):
        """Test that unknown models raise appropriate errors"""
        from src.openwebui_service.llm_proxy import choose_backend
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException) as exc_info:
            choose_backend("unknown-model")
        
        assert exc_info.value.status_code == 400
        assert "Unknown model" in str(exc_info.value.detail)
    
    @patch('httpx.AsyncClient.post')
    async def test_chat_completions_endpoint_success(self, mock_post):
        """Test successful chat completions request"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "test-completion",
            "object": "chat.completion",
            "model": "gpt-3.5-turbo",
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_post.return_value = mock_response
        
        # Test request
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            response = self.client.post(
                "/v1/chat/completions",
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Hello"}]
                },
                headers={"Authorization": "Bearer test-key"}
            )
        
        assert response.status_code == 200
        assert "test-completion" in response.json().get("id", "")
    
    def test_missing_api_keys_handling(self):
        """Test handling of missing API keys"""        
        with patch.dict(os.environ, {}, clear=True):
            # Test that app still starts but with default values
            from src.openwebui_service.llm_proxy import OPENAI_API_KEY, GROQ_API_KEY, CLAUDE_API_KEY, GEMINI_API_KEY
            
            assert OPENAI_API_KEY == "sk-xxxx"  # Default value
            assert GROQ_API_KEY == "gsk-xxxx"   # Default value
            assert CLAUDE_API_KEY == "sk-ant-xxx"  # Default value
            assert GEMINI_API_KEY == "AIza..."   # Default value
    
    @pytest.mark.parametrize("backend_name", ["openai", "groq", "claude", "gemini"])
    def test_backend_endpoints_format(self, backend_name):
        """Test that backend URLs are correctly formatted"""
        backend = self.backends[backend_name]
        base_url = backend["base_url"]
        
        # Check that base_url is properly formatted
        assert base_url.startswith("https://")
        assert "chat/completions" in base_url or "completions" in base_url
    
    def test_backends_json_structure(self):
        """Test the overall structure of backends.json"""
        # Test top-level structure
        assert "backends" in self.config
        assert "proxy" in self.config
        
        # Test proxy configuration
        proxy = self.config["proxy"]
        required_proxy_fields = ["host", "port", "health_endpoint", "main_endpoint"]
        for field in required_proxy_fields:
            assert field in proxy
        
        # Test that all expected backends exist
        expected_backends = ["openai", "groq", "claude", "gemini"]
        for backend in expected_backends:
            assert backend in self.backends
    
    def test_model_coverage(self):
        """Test that models from backends.example.json are covered by routing logic"""
        from src.openwebui_service.llm_proxy import choose_backend, BACKENDS_CONFIG
        
        # Test each backend's models from the loaded configuration
        backends = BACKENDS_CONFIG.get("backends", {})
        for backend_name, backend_config in backends.items():
            models = backend_config.get("models", [])
            api_key_env = backend_config.get("api_key_env", f"{backend_name.upper()}_API_KEY")
            
            # Set up mock environment
            with patch.dict(os.environ, {api_key_env: 'test-key'}):
                for model in models:
                    try:
                        backend = choose_backend(model)
                        assert backend is not None
                        assert "base_url" in backend
                        assert "api_key" in backend
                        assert "headers" in backend
                        assert "backend_name" in backend
                        assert backend["backend_name"] == backend_name
                    except Exception as e:
                        pytest.fail(f"Model {model} from {backend_name} failed routing: {e}")
    
    def test_model_aliases(self):
        """Test that model aliases work correctly"""
        from src.openwebui_service.llm_proxy import get_backend_for_model, BACKENDS_CONFIG
        
        model_aliases = BACKENDS_CONFIG.get("model_aliases", {})
        for alias, target_model in model_aliases.items():
            try:
                # Both alias and target should resolve to the same backend
                alias_backend = get_backend_for_model(alias)
                target_backend = get_backend_for_model(target_model)
                assert alias_backend == target_backend
            except Exception as e:
                pytest.fail(f"Alias {alias} -> {target_model} failed: {e}")
    
    def test_backend_headers_template(self):
        """Test that backend headers are properly formatted"""
        from src.openwebui_service.llm_proxy import choose_backend, BACKENDS_CONFIG
        
        backends = BACKENDS_CONFIG.get("backends", {})
        for backend_name, backend_config in backends.items():
            api_key_env = backend_config.get("api_key_env", f"{backend_name.upper()}_API_KEY")
            models = backend_config.get("models", [])
            
            if not models:
                continue
                
            with patch.dict(os.environ, {api_key_env: 'test-api-key'}):
                try:
                    backend = choose_backend(models[0])  # Test with first model
                    headers = backend.get("headers", {})
                    
                    # Check that headers contain properly formatted authorization
                    assert "Authorization" in headers
                    auth_header = headers["Authorization"]
                    assert "test-api-key" in auth_header
                    assert "{api_key}" not in auth_header  # Should be formatted
                except Exception as e:
                    pytest.fail(f"Backend {backend_name} headers formatting failed: {e}")
    
    def test_models_endpoint(self):
        """Test the /v1/models endpoint"""
        response = self.client.get("/v1/models")
        assert response.status_code == 200
        
        data = response.json()
        assert "object" in data
        assert "data" in data
        assert data["object"] == "list"
        assert isinstance(data["data"], list)
        
        # Check that we have some models
        assert len(data["data"]) > 0
        
        # Check model structure
        for model in data["data"]:
            assert "id" in model
            assert "object" in model
            assert "backend" in model
            assert model["object"] == "model"


class TestLLMProxyIntegration:
    """Integration tests for LLM Proxy with external APIs"""
    
    def setup_class(self):
        """Setup integration test class"""
        self.client = TestClient(app)
    
    @pytest.mark.integration
    @pytest.mark.skipif(not os.getenv('OPENAI_API_KEY'), reason="OpenAI API key not available")
    def test_real_openai_api_call(self):
        """Test real API call to OpenAI (requires API key)"""
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Say hello"}],
                "max_tokens": 10
            },
            headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"}
        )
        
        # Should get a response (might be rate limited, but should be valid)
        assert response.status_code in [200, 429, 401]  # Success, rate limit, or auth error
    
    @pytest.mark.integration  
    @pytest.mark.skipif(not os.getenv('GROQ_API_KEY'), reason="Groq API key not available")
    def test_real_groq_api_call(self):
        """Test real API call to Groq (requires API key)"""
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "llama-3.1-70b-versatile",
                "messages": [{"role": "user", "content": "Say hello"}],
                "max_tokens": 10
            },
            headers={"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"}
        )
        
        assert response.status_code in [200, 429, 401]


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])