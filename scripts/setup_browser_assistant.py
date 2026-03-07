#!/usr/bin/env python3
"""Optional standalone utility: manually pre-create the bb-browser-agent assistant.

The app creates this automatically on first use (per API key).
Run this only if you want to pre-create it before starting the server.

Usage:
    BACKBOARD_API_KEY=your_key uv run python scripts/setup_browser_assistant.py
"""
import asyncio
import os
import sys


async def main():
    api_key = os.getenv("BACKBOARD_API_KEY")
    if not api_key:
        print("ERROR: Set BACKBOARD_API_KEY in your environment.")
        sys.exit(1)

    # Import tool definitions from the app
    sys.path.insert(0, str(__file__.replace("/scripts/setup_browser_assistant.py", "")))
    from app.api.chat import _BROWSER_TOOLS, _SYSTEM_PROMPT

    from backboard import BackboardClient

    print("Creating bb-browser-agent...")
    async with BackboardClient(api_key=api_key) as client:
        assistant = await client.create_assistant(
            name="bb-browser-agent",
            system_prompt=_SYSTEM_PROMPT,
            tools=_BROWSER_TOOLS,
        )
    print(f"✓ Created: {assistant.assistant_id}")


if __name__ == "__main__":
    asyncio.run(main())
