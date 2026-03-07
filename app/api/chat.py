"""Chat blueprint — Browser Assistant with Backboard readonly tools."""
import asyncio
import json

from flask import Blueprint, Response, jsonify, request, session, stream_with_context

chat_bp = Blueprint("chat", __name__)

# ---------------------------------------------------------------------------
# Browser assistant definition (tools + system prompt)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are the Backboard Browser Assistant — an intelligent guide to the user's Backboard.io workspace. You have readonly access to their assistants, threads, documents, and memories through tools.

Be concise but informative. When listing resources, present them in clean markdown. Always use tools rather than guessing data.

You can help the user:
- Explore and summarize their assistants and configurations
- Browse conversation threads and their messages
- Search and list memories across assistants
- Find and describe documents
- Provide counts and summaries about their workspace

When presenting lists, use **bold names** with key metadata on the same line. Include IDs when the user might want to drill in further. For long lists, offer to filter or search."""

_BROWSER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_assistants",
            "description": "List all Backboard assistants with metadata (name, model, system prompt preview, tool count, creation date).",
            "parameters": {
                "type": "object",
                "properties": {
                    "skip": {"type": "integer", "description": "Number to skip (default 0)"},
                    "limit": {"type": "integer", "description": "Max to return, 0 = all (default 0)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_assistant",
            "description": "Get full details of a specific assistant including system prompt and tool definitions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "assistant_id": {"type": "string", "description": "The assistant ID"},
                },
                "required": ["assistant_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_threads",
            "description": "List conversation threads, optionally filtered by assistant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "assistant_id": {"type": "string", "description": "Filter by assistant ID (optional)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_thread",
            "description": "Get a specific thread with all its messages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "The thread ID"},
                },
                "required": ["thread_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_memories",
            "description": "List all memories stored on a specific assistant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "assistant_id": {"type": "string", "description": "The assistant ID"},
                },
                "required": ["assistant_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memories",
            "description": "Semantic search across memories of a specific assistant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "assistant_id": {"type": "string", "description": "The assistant ID to search memories in"},
                    "query": {"type": "string", "description": "The semantic search query"},
                },
                "required": ["assistant_id", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "List all uploaded documents with metadata (name, status, size, creation date).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_assistant_counts",
            "description": "Get thread and memory counts for one or more assistants.",
            "parameters": {
                "type": "object",
                "properties": {
                    "assistant_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of assistant IDs to get counts for",
                    },
                },
                "required": ["assistant_ids"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Lazy per-API-key browser assistant (in-memory cache, no .env writes)
# ---------------------------------------------------------------------------

# Keyed by api_key → assistant_id. Survives for the server process lifetime.
_browser_assistant_cache: dict = {}


def _get_or_create_browser_assistant_id(api_key: str) -> str:
    """Return the cached browser assistant ID for this API key, creating it if needed."""
    if api_key in _browser_assistant_cache:
        return _browser_assistant_cache[api_key]

    async def _create():
        from backboard import BackboardClient

        async with BackboardClient(api_key=api_key) as client:
            assistant = await client.create_assistant(
                name="bb-browser-agent",
                system_prompt=_SYSTEM_PROMPT,
                tools=_BROWSER_TOOLS,
            )
            return assistant.assistant_id

    assistant_id = asyncio.run(_create())
    _browser_assistant_cache[api_key] = assistant_id
    return assistant_id


def _get_service():
    from app.services.backboard import BackboardService

    api_key = session.get("backboard_api_key")
    if not api_key:
        raise ValueError("Not authenticated")
    return BackboardService(api_key=api_key)


# ---------------------------------------------------------------------------
# Thread management
# ---------------------------------------------------------------------------


@chat_bp.route("/api/chat/thread/new", methods=["POST"])
def new_thread():
    try:
        api_key = session.get("backboard_api_key")
        if not api_key:
            return jsonify({"error": "Not authenticated"}), 401
        from app.services.backboard import BackboardService
        service = BackboardService(api_key=api_key)
        assistant_id = _get_or_create_browser_assistant_id(api_key)
        thread = service.create_thread(assistant_id)
        return jsonify({"thread_id": thread.id})
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/api/chat/thread/messages", methods=["GET"])
def get_messages():
    try:
        service = _get_service()
        thread_id = request.args.get("thread_id")
        if not thread_id:
            return jsonify({"messages": []})

        thread = service.get_thread(thread_id)
        messages = []
        for msg in thread.messages or []:
            if hasattr(msg, "model_dump"):
                d = msg.model_dump()
            elif isinstance(msg, dict):
                d = msg
            else:
                continue
            # Only surface user/assistant turns to the chat UI
            role = str(d.get("role", "")).lower()
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": str(d.get("content", ""))})
        return jsonify({"messages": messages, "thread_id": thread_id})
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------


def _execute_tool(name: str, args: dict, service) -> str:
    """Execute a readonly browser tool and return a JSON string."""
    try:
        if name == "list_assistants":
            assistants = service.list_assistants(
                skip=args.get("skip", 0),
                limit=args.get("limit", 0),
            )
            result = []
            for a in assistants:
                d = a.model_dump()
                # Truncate long system prompts
                if d.get("system_prompt") and len(d["system_prompt"]) > 200:
                    d["system_prompt"] = d["system_prompt"][:200] + "…"
                result.append(d)
            return json.dumps({"assistants": result, "count": len(result)}, default=str)

        elif name == "get_assistant":
            assistant = service.get_assistant(args["assistant_id"])
            return json.dumps(assistant.model_dump(), default=str)

        elif name == "list_threads":
            threads = service.list_threads(assistant_id=args.get("assistant_id"))
            result = []
            for t in threads:
                d = t.model_dump()
                d["message_count"] = len(d.get("messages") or [])
                d["messages"] = []  # omit full message content from list
                result.append(d)
            return json.dumps({"threads": result, "count": len(result)}, default=str)

        elif name == "get_thread":
            thread = service.get_thread(args["thread_id"])
            d = thread.model_dump()
            # Serialize messages with only role+content
            msgs = []
            for m in d.get("messages") or []:
                role = str(m.get("role", "")).lower() if isinstance(m, dict) else ""
                content = m.get("content", "") if isinstance(m, dict) else ""
                if role in ("user", "assistant"):
                    msgs.append({"role": role, "content": str(content)})
            d["messages"] = msgs
            return json.dumps(d, default=str)

        elif name == "list_memories":
            memories = service.list_memories(args["assistant_id"])
            result = [m.model_dump() for m in memories]
            return json.dumps({"memories": result, "count": len(result)}, default=str)

        elif name == "search_memories":
            from app.models.memory import MemorySearch

            search = MemorySearch(query=args["query"])
            memories = service.search_memory(search, args["assistant_id"])
            result = [m.model_dump() for m in memories]
            return json.dumps({"memories": result, "count": len(result)}, default=str)

        elif name == "list_documents":
            documents = service.list_documents()
            result = [d.model_dump() for d in documents]
            return json.dumps({"documents": result, "count": len(result)}, default=str)

        elif name == "get_assistant_counts":
            counts = service.get_assistant_counts(args["assistant_ids"])
            return json.dumps(counts, default=str)

        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    except Exception as e:
        return json.dumps({"error": str(e)})


def _tool_summary(name: str, result_str: str) -> str:
    """Short human-readable summary of a tool result for the UI pill."""
    try:
        result = json.loads(result_str)
        if name == "list_assistants":
            return f"{result.get('count', 0)} assistants"
        elif name == "get_assistant":
            return result.get("name", "assistant")
        elif name == "list_threads":
            return f"{result.get('count', 0)} threads"
        elif name == "get_thread":
            return f"{len(result.get('messages', []))} messages"
        elif name == "list_memories":
            return f"{result.get('count', 0)} memories"
        elif name == "search_memories":
            return f"{result.get('count', 0)} results"
        elif name == "list_documents":
            return f"{result.get('count', 0)} documents"
        elif name == "get_assistant_counts":
            return f"{len(result)} assistants"
        return "done"
    except Exception:
        return "done"


# ---------------------------------------------------------------------------
# SSE send endpoint
# ---------------------------------------------------------------------------


@chat_bp.route("/api/chat/send", methods=["POST"])
def send_message():
    # Capture request-scoped values before generator starts
    api_key = session.get("backboard_api_key")
    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    thread_id = (data.get("thread_id") or "").strip()

    def generate():
        def emit(obj: dict) -> str:
            return f"data: {json.dumps(obj)}\n\n"

        if not api_key:
            yield emit({"type": "error", "text": "Not authenticated. Enter your API key first."})
            return

        if not content:
            yield emit({"type": "error", "text": "Empty message."})
            return

        try:
            assistant_id = _get_or_create_browser_assistant_id(api_key)
            from app.services.backboard import BackboardService

            service = BackboardService(api_key=api_key)

            # Create thread if none supplied
            active_thread_id = thread_id
            if not active_thread_id:
                thread = service.create_thread(assistant_id)
                active_thread_id = thread.id
                yield emit({"type": "thread_created", "thread_id": active_thread_id})

            yield emit({"type": "status", "text": "Thinking…"})

            response = service.add_message(active_thread_id, content)

            # Tool-call loop
            iterations = 0
            max_iterations = 10
            while (
                response.get("status") == "REQUIRES_ACTION"
                and response.get("tool_calls")
                and iterations < max_iterations
            ):
                tool_outputs = []

                for tc in response["tool_calls"]:
                    # Normalize tool call dict (handles both Pydantic-dumped and raw dicts)
                    if isinstance(tc, dict):
                        fn = tc.get("function") or {}
                        tool_name = fn.get("name", "")
                        raw_args = fn.get("parsed_arguments") or fn.get("arguments") or {}
                        tool_call_id = tc.get("id", "")
                    else:
                        fn = getattr(tc, "function", None)
                        tool_name = getattr(fn, "name", "") if fn else ""
                        raw_args = getattr(fn, "parsed_arguments", None) or {}
                        tool_call_id = getattr(tc, "id", "")

                    if isinstance(raw_args, str):
                        try:
                            raw_args = json.loads(raw_args)
                        except Exception:
                            raw_args = {}

                    yield emit({"type": "tool_start", "name": tool_name})

                    result = _execute_tool(tool_name, raw_args, service)
                    summary = _tool_summary(tool_name, result)

                    yield emit({"type": "tool_done", "name": tool_name, "summary": summary})

                    tool_outputs.append({"tool_call_id": tool_call_id, "output": result})

                run_id = response.get("run_id") or ""
                response = service.submit_tool_outputs(active_thread_id, run_id, tool_outputs)
                iterations += 1

            final_text = response.get("content") or ""
            if final_text:
                yield emit({"type": "content", "text": final_text})

            yield emit({"type": "done"})

        except Exception as e:
            yield emit({"type": "error", "text": str(e)})

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
