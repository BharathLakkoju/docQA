"""Shared per-node AST-chunking logic for n8n workflow JSON, used by both the
official template API ingester and the awesome-n8n-templates mirror ingester
so the two sources produce identically-shaped chunks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.chunk_ids import stable_chunk_id  # noqa: E402

TRIGGER_MARKERS = ("trigger", "webhook")


def is_trigger_node(node_type: str) -> bool:
    lowered = node_type.lower()
    return any(marker in lowered for marker in TRIGGER_MARKERS)


def outgoing_targets(connections: dict, node_name: str) -> list[str]:
    """n8n connections are keyed by *source node name* ->
    {output_type: [[{node: target_name, ...}], ...]}.
    """
    targets: list[str] = []
    entry = connections.get(node_name)
    if not entry:
        return targets
    for output_branches in entry.values():
        for branch in output_branches:
            for conn in branch:
                if not isinstance(conn, dict):
                    continue
                target = conn.get("node")
                if target:
                    targets.append(target)
    return targets


def node_to_chunk(
    template_id,
    template_name: str,
    categories: list[str],
    node: dict,
    connections: dict,
    source: str,
    source_url: str,
    license_: str,
) -> dict:
    node_name = node.get("name", "")
    node_type = node.get("type", "")
    params = node.get("parameters", {})
    creds = node.get("credentials", {})
    credential_types = sorted(creds.keys()) if isinstance(creds, dict) else []
    targets = outgoing_targets(connections, node_name)

    params_json = json.dumps(params, ensure_ascii=False, indent=2)
    if len(params_json) > 4000:
        params_json = params_json[:4000] + "\n... (truncated)"

    text_parts = [
        f"Workflow: {template_name} (n8n template #{template_id})",
        f"Node: {node_name}",
        f"Node type: {node_type}",
    ]
    if credential_types:
        text_parts.append(f"Credential types used: {', '.join(credential_types)}")
    if targets:
        text_parts.append(f"Connects to: {', '.join(targets)}")
    text_parts.append(f"Parameters:\n{params_json}")
    text = "\n".join(text_parts)

    return {
        "id": stable_chunk_id("n8n-node", source, str(template_id), node.get("id", node_name)),
        "text": text,
        "metadata": {
            "domain": "n8n",
            "artifact_type": "workflow_node",
            "template_id": template_id,
            "template_name": template_name,
            "categories": categories,
            "node_name": node_name,
            "node_type": node_type,
            "is_trigger": is_trigger_node(node_type),
            "credential_types": credential_types,
            "connects_to": targets,
            "source": source,
            "source_url": source_url,
            "license": license_,
        },
    }


def chunk_workflow(
    inner: dict,
    template_id,
    template_name: str,
    categories: list[str],
    source: str,
    source_url: str,
    license_: str,
) -> list[dict]:
    nodes = inner.get("nodes", [])
    connections = inner.get("connections", {})
    return [
        node_to_chunk(template_id, template_name, categories, node, connections, source, source_url, license_)
        for node in nodes
        if node.get("name")
    ]
