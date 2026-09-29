from __future__ import annotations

import argparse
import json
from typing import Any


def _obj(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


_FUNCTIONS: list[dict[str, Any]] = [
    {
        "name": "melodex_status",
        "description": "Get the current Melodex playback state, current track, queue, volume and position.",
        "parameters": _obj({}, []),
    },
    {
        "name": "melodex_sources",
        "description": "List connected Melodex music sources in resolver-priority order, including version, declared permissions and install provenance when available.",
        "parameters": _obj({}, []),
    },
    {
        "name": "melodex_extensions",
        "description": "List installed Melodex capability extensions for identity, metadata, artwork and lyrics, including declared permissions and install provenance.",
        "parameters": _obj({}, []),
    },
    {
        "name": "melodex_search",
        "description": "Search connected Melodex sources for tracks.",
        "parameters": _obj(
            {
                "query": {"type": "string"},
                "provider": {"type": ["string", "null"], "description": "Provider id, 'all', or null for all."},
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 100},
            },
            ["query", "provider", "limit"],
        ),
    },
    {
        "name": "melodex_recommendations",
        "description": "Get provider-side track recommendations from a seed artist/title. Results may need resolving through another playback source.",
        "parameters": _obj(
            {
                "artist": {"type": "string"},
                "title": {"type": "string"},
                "album": {"type": ["string", "null"]},
                "provider": {"type": ["string", "null"]},
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 100},
            },
            ["artist", "title", "album", "provider", "limit"],
        ),
    },
    {
        "name": "melodex_resolve",
        "description": "Resolve artist/title/album metadata to Melodex's best playable source without changing playback.",
        "parameters": _obj(
            {
                "artist": {"type": "string"},
                "title": {"type": "string"},
                "album": {"type": ["string", "null"]},
            },
            ["artist", "title", "album"],
        ),
    },
    {
        "name": "melodex_resolution_candidates",
        "description": "Inspect ranked source matches and resolver scores for a requested song.",
        "parameters": _obj(
            {
                "artist": {"type": "string"},
                "title": {"type": "string"},
                "album": {"type": ["string", "null"]},
                "limit": {"type": ["integer", "null"], "minimum": 1, "maximum": 50},
            },
            ["artist", "title", "album", "limit"],
        ),
    },
    {
        "name": "melodex_play",
        "description": "Resolve one requested track, replace the queue with it and start playback.",
        "parameters": _obj(
            {
                "artist": {"type": "string"},
                "title": {"type": "string"},
                "album": {"type": ["string", "null"]},
            },
            ["artist", "title", "album"],
        ),
    },
    {
        "name": "melodex_queue",
        "description": "Resolve and queue an ordered list of requested tracks.",
        "parameters": _obj(
            {
                "tracks": {
                    "type": "array",
                    "minItems": 1,
                    "items": _obj(
                        {
                            "artist": {"type": "string"},
                            "title": {"type": "string"},
                            "album": {"type": ["string", "null"]},
                        },
                        ["artist", "title", "album"],
                    ),
                },
                "replace": {"type": "boolean"},
                "autoplay": {"type": "boolean"},
            },
            ["tracks", "replace", "autoplay"],
        ),
    },
    {
        "name": "melodex_playback",
        "description": "Control current playback or clear the queue.",
        "parameters": _obj(
            {"action": {"type": "string", "enum": ["play_pause", "next", "previous", "stop", "clear_queue"]}},
            ["action"],
        ),
    },
    {
        "name": "melodex_seek",
        "description": "Seek the current track to an absolute position in seconds.",
        "parameters": _obj({"position_seconds": {"type": "number", "minimum": 0}}, ["position_seconds"]),
    },
    {
        "name": "melodex_volume",
        "description": "Set Melodex playback volume from 0.0 to 1.0.",
        "parameters": _obj({"volume": {"type": "number", "minimum": 0, "maximum": 1}}, ["volume"]),
    },
    {
        "name": "melodex_flow",
        "description": "Ask Melodex Flow to reorder the current queue for smoother transitions.",
        "parameters": _obj({}, []),
    },
    {
        "name": "melodex_feedback",
        "description": "Record taste feedback for the current track.",
        "parameters": _obj({"action": {"type": "string", "enum": ["love", "dislike", "keep"]}}, ["action"]),
    },
    {
        "name": "melodex_save_moment",
        "description": "Bookmark the current playback position with an optional note.",
        "parameters": _obj({"label": {"type": ["string", "null"]}}, ["label"]),
    },
]


CHAT_COMPLETIONS_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": f["name"],
            "description": f["description"],
            "parameters": f["parameters"],
            "strict": True,
        },
    }
    for f in _FUNCTIONS
]

RESPONSES_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": f["name"],
        "description": f["description"],
        "parameters": f["parameters"],
        "strict": True,
    }
    for f in _FUNCTIONS
]

OPENAI_FUNCTION_TOOLS = {
    "chat_completions": CHAT_COMPLETIONS_TOOLS,
    "responses": RESPONSES_TOOLS,
}


def execute_tool(client: Any, name: str, arguments: dict[str, Any] | None = None) -> Any:
    args = dict(arguments or {})
    if name == "melodex_status":
        return client.status()
    if name == "melodex_sources":
        return client.providers()
    if name == "melodex_extensions":
        return client.extensions()
    if name == "melodex_search":
        provider = str(args.get("provider") or "all")
        limit = int(args.get("limit") or 20)
        return client.search(str(args["query"]), provider, limit)
    if name == "melodex_recommendations":
        provider = str(args.get("provider") or "all")
        limit = int(args.get("limit") or 20)
        return client.recommendations(
            str(args["artist"]),
            str(args["title"]),
            str(args.get("album") or ""),
            provider,
            limit,
        )
    if name == "melodex_resolve":
        return client.resolve(str(args["artist"]), str(args["title"]), str(args.get("album") or ""))
    if name == "melodex_resolution_candidates":
        return client.resolve_candidates(
            str(args["artist"]),
            str(args["title"]),
            str(args.get("album") or ""),
            int(args.get("limit") or 12),
        )
    if name == "melodex_play":
        return client.play(str(args["artist"]), str(args["title"]), str(args.get("album") or ""))
    if name == "melodex_queue":
        return client.queue_tracks(
            [dict(x) for x in list(args.get("tracks") or []) if isinstance(x, dict)],
            replace=bool(args.get("replace", True)),
            autoplay=bool(args.get("autoplay", True)),
        )
    if name == "melodex_playback":
        return client.control(str(args["action"]))
    if name == "melodex_seek":
        return client.control("seek_ms", value=max(0, int(float(args["position_seconds"]) * 1000)))
    if name == "melodex_volume":
        return client.control("set_volume", value=max(0.0, min(1.0, float(args["volume"]))))
    if name == "melodex_flow":
        return client.control("flow_queue")
    if name == "melodex_feedback":
        mapping = {"love": "love_current", "dislike": "dislike_current", "keep": "keep_current"}
        return client.control(mapping[str(args["action"])])
    if name == "melodex_save_moment":
        return client.control("save_moment", label=str(args.get("label") or ""))
    raise ValueError(f"Unknown Melodex tool: {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect or execute Melodex OpenAI function tools.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="Print tool definitions as JSON.")
    p_list.add_argument("--format", choices=["chat", "responses", "all"], default="all")

    p_call = sub.add_parser("call", help="Execute one tool against a running Melodex app.")
    p_call.add_argument("name")
    p_call.add_argument("arguments", nargs="?", default="{}", help="JSON object with tool arguments")

    args = parser.parse_args(argv)

    if args.command == "list":
        payload = (
            CHAT_COMPLETIONS_TOOLS
            if args.format == "chat"
            else RESPONSES_TOOLS
            if args.format == "responses"
            else OPENAI_FUNCTION_TOOLS
        )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    from .control_client import MelodexControlClient

    client = MelodexControlClient.from_state()
    arguments = json.loads(args.arguments)
    if not isinstance(arguments, dict):
        raise SystemExit("arguments must be a JSON object")
    result = execute_tool(client, args.name, arguments)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
