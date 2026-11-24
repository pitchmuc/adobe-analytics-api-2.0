"""Opt-in stdio bridge for clients that cannot complete SDK 2.x discovery."""

import json
import subprocess
import sys
import threading
from typing import BinaryIO


def relay_legacy_stdio(
    command: list[str], input_stream: BinaryIO, output_stream: BinaryIO
) -> int:
    """Reject discovery probes before they lock the child into the modern protocol."""
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    output_lock = threading.Lock()

    def write_output(data: bytes) -> None:
        with output_lock:
            output_stream.write(data)
            output_stream.flush()

    def forward_input() -> None:
        try:
            for line in input_stream:
                try:
                    message = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    message = None
                if (
                    isinstance(message, dict)
                    and message.get("method") == "server/discover"
                    and "id" in message
                ):
                    response = {
                        "jsonrpc": "2.0",
                        "id": message["id"],
                        "error": {
                            "code": -32601,
                            "message": (
                                "server/discover is unavailable in legacy stdio mode; "
                                "use initialize."
                            ),
                        },
                    }
                    write_output(json.dumps(response).encode("utf-8") + b"\n")
                else:
                    process.stdin.write(line)
                    process.stdin.flush()
        except BrokenPipeError:
            print("MCP child closed its input stream.", file=sys.stderr)
        finally:
            process.stdin.close()

    input_thread = threading.Thread(target=forward_input, daemon=True)
    input_thread.start()
    try:
        for line in process.stdout:
            write_output(line)
        return process.wait()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        input_thread.join(timeout=1)
        process.stdout.close()
