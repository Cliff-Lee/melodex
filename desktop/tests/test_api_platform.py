from melodex.api_schema import openapi_document
from melodex.openai_tools import CHAT_COMPLETIONS_TOOLS, RESPONSES_TOOLS, execute_tool
from melodex.llm_bridge import LLMClient


def test_openapi_has_control_surface():
    doc = openapi_document()
    expected = {
        "/health",
        "/openapi.json",
        "/v1/providers",
        "/v1/extensions",
        "/v1/search",
        "/v1/resolve",
        "/v1/resolve-candidates",
        "/v1/status",
        "/v1/play",
        "/v1/queue",
        "/v1/control",
        "/v1/media",
        "/v1/openai/tools",
    }
    assert expected.issubset(doc["paths"])


def test_openai_tool_dialects_cover_same_names():
    chat_names = {item["function"]["name"] for item in CHAT_COMPLETIONS_TOOLS}
    response_names = {item["name"] for item in RESPONSES_TOOLS}
    assert chat_names == response_names
    assert "melodex_search" in chat_names
    assert "melodex_extensions" in chat_names
    assert "melodex_play" in chat_names


def test_strict_tool_schemas_meet_openai_requirements():
    def check_object(schema):
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert set(schema.get("properties") or {}) == set(schema.get("required") or [])
        for prop in (schema.get("properties") or {}).values():
            if isinstance(prop, dict) and prop.get("type") == "object":
                check_object(prop)
            if isinstance(prop, dict) and prop.get("type") == "array":
                items = prop.get("items")
                if isinstance(items, dict) and items.get("type") == "object":
                    check_object(items)

    for item in CHAT_COMPLETIONS_TOOLS:
        fn = item["function"]
        assert fn["strict"] is True
        check_object(fn["parameters"])


class FakeClient:
    def search(self, query, provider="all", limit=20):
        return [{"query": query, "provider": provider, "limit": limit}]

    def control(self, action, **args):
        return {"action": action, "args": args}


def test_tool_executor_defaults_and_clamps():
    client = FakeClient()
    result = execute_tool(client, "melodex_search", {"query": "ambient", "provider": None, "limit": None})
    assert result[0]["provider"] == "all"
    assert result[0]["limit"] == 20

    result = execute_tool(client, "melodex_volume", {"volume": 2})
    assert result["action"] == "set_volume"
    assert result["args"]["value"] == 1.0


def test_openai_responses_support():
    assert LLMClient.default_endpoint("openai").endswith("/v1/responses")
    assert LLMClient._responses_text({"output_text": "hello"}) == "hello"
    payload = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "from block"}],
            }
        ]
    }
    assert LLMClient._responses_text(payload) == "from block"
