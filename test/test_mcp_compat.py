import io
import json
import sys

from aanalytics2.mcp_compat import relay_legacy_stdio


def test_legacy_bridge_rejects_discovery_and_preserves_other_messages():
    messages = [
        {
            "jsonrpc": "2.0",
            "id": "probe",
            "method": "server/discover",
            "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}},
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {"protocolVersion": "2025-11-25"},
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "caf\u00e9"}},
    ]
    lines = [json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n" for message in messages]
    invalid = b"invalid json\n"
    output = io.BytesIO()

    code = relay_legacy_stdio(
        [sys.executable, "-u", "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"],
        io.BytesIO(b"".join(lines) + invalid),
        output,
    )

    assert code == 0
    results = output.getvalue().splitlines(keepends=True)
    rejection = json.loads(results[0])
    assert rejection["id"] == "probe"
    assert rejection["error"]["code"] == -32601
    assert results[1:] == lines[1:] + [invalid]


def test_legacy_bridge_preserves_child_failure():
    assert relay_legacy_stdio(
        [sys.executable, "-c", "raise SystemExit(7)"], io.BytesIO(), io.BytesIO()
    ) == 7
