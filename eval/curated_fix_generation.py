"""Hand-curated fix-generation eval items. Each gold_fix is real config,
in the conventions actually observed across the ingested corpus (action
versions, node type strings) — and every one is validated by the actual
actionlint / n8n-schema validators at eval-build time (see
verify_gold_fixes.py), not just eyeballed. A gold answer that doesn't pass
its own validator would make the eval set dishonest, so that check is not
optional.
"""

FIX_GENERATION_ITEMS = [
    {
        "domain": "github_actions",
        "task_type": "fix_generation",
        "query": "Write a GitHub Actions job that checks out the repo, sets up Node 20, installs deps with npm ci, and runs npm test, triggered on push and pull_request.",
        "gold_fix": """name: CI
on:
  push:
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm ci
      - run: npm test
""",
    },
    {
        "domain": "github_actions",
        "task_type": "fix_generation",
        "query": "Write a GitHub Actions job that runs pytest across a matrix of Python 3.11 and 3.12 on ubuntu-latest.",
        "gold_fix": """name: CI
on: push
jobs:
  pytest:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements.txt
      - run: pytest
""",
    },
    {
        "domain": "github_actions",
        "task_type": "fix_generation",
        "query": "Write a GitHub Actions job that builds a Docker image with docker/build-push-action and pushes it to ghcr.io on push to main.",
        "gold_fix": """name: Docker Publish
on:
  push:
    branches:
      - main
jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ghcr.io/${{ github.repository }}:latest
""",
    },
    {
        "domain": "github_actions",
        "task_type": "fix_generation",
        "query": "Write a GitHub Actions job that only runs on workflow_dispatch and deploys to production using an environment named 'production'.",
        "gold_fix": """name: Deploy
on: workflow_dispatch
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4
      - run: echo "deploying"
""",
    },
    {
        "domain": "github_actions",
        "task_type": "fix_generation",
        "query": "Write a GitHub Actions job that caches npm dependencies using actions/cache keyed on package-lock.json, then installs and builds.",
        "gold_fix": """name: Build
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/cache@v4
        with:
          path: ~/.npm
          key: ${{ runner.os }}-npm-${{ hashFiles('package-lock.json') }}
      - run: npm ci
      - run: npm run build
""",
    },
    {
        "domain": "github_actions",
        "task_type": "fix_generation",
        "query": "Write a GitHub Actions job named 'lint' that runs golangci-lint on ubuntu-latest for a Go project, triggered on pull_request.",
        "gold_fix": """name: Lint
on: pull_request
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: "1.22"
      - uses: golangci/golangci-lint-action@v6
""",
    },
    {
        "domain": "n8n",
        "task_type": "fix_generation",
        "query": "Write a minimal n8n workflow JSON with a Manual Trigger node connected to a Set node that assigns a field 'status' with value 'ok'.",
        "gold_fix": """{
  "name": "Status check",
  "nodes": [
    {"id": "1", "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "position": [0, 0], "parameters": {}},
    {"id": "2", "name": "Set Status", "type": "n8n-nodes-base.set", "position": [200, 0], "parameters": {"assignments": {"assignments": [{"id": "a1", "name": "status", "type": "string", "value": "ok"}]}}}
  ],
  "connections": {"Manual Trigger": {"main": [[{"node": "Set Status", "type": "main", "index": 0}]]}}
}""",
    },
    {
        "domain": "n8n",
        "task_type": "fix_generation",
        "query": "Write an n8n workflow JSON with a Schedule Trigger (every hour) connected to an HTTP Request node that GETs https://api.example.com/health.",
        "gold_fix": """{
  "name": "Hourly health check",
  "nodes": [
    {"id": "1", "name": "Schedule Trigger", "type": "n8n-nodes-base.scheduleTrigger", "position": [0, 0], "parameters": {"rule": {"interval": [{"field": "hours", "hoursInterval": 1}]}}},
    {"id": "2", "name": "HTTP Request", "type": "n8n-nodes-base.httpRequest", "position": [200, 0], "parameters": {"url": "https://api.example.com/health", "method": "GET"}}
  ],
  "connections": {"Schedule Trigger": {"main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]}}
}""",
    },
    {
        "domain": "n8n",
        "task_type": "fix_generation",
        "query": "Write an n8n workflow JSON with a Webhook Trigger connected to an IF node that checks whether the incoming JSON field 'status' equals 'active'.",
        "gold_fix": """{
  "name": "Webhook status filter",
  "nodes": [
    {"id": "1", "name": "Webhook Trigger", "type": "n8n-nodes-base.webhook", "position": [0, 0], "parameters": {"path": "status-check", "httpMethod": "POST"}},
    {"id": "2", "name": "If Active", "type": "n8n-nodes-base.if", "position": [200, 0], "parameters": {"conditions": {"conditions": [{"leftValue": "={{ $json.status }}", "rightValue": "active", "operator": {"type": "string", "operation": "equals"}}]}}}
  ],
  "connections": {"Webhook Trigger": {"main": [[{"node": "If Active", "type": "main", "index": 0}]]}}
}""",
    },
    {
        "domain": "n8n",
        "task_type": "fix_generation",
        "query": "Write an n8n workflow JSON with an Error Trigger node connected to a Slack node that would post a message (leave parameters minimal).",
        "gold_fix": """{
  "name": "Error notifier",
  "nodes": [
    {"id": "1", "name": "Error Trigger", "type": "n8n-nodes-base.errorTrigger", "position": [0, 0], "parameters": {}},
    {"id": "2", "name": "Slack", "type": "n8n-nodes-base.slack", "position": [200, 0], "parameters": {"text": "A workflow failed"}}
  ],
  "connections": {"Error Trigger": {"main": [[{"node": "Slack", "type": "main", "index": 0}]]}}
}""",
    },
    {
        "domain": "n8n",
        "task_type": "fix_generation",
        "query": "Write an n8n workflow JSON with a Manual Trigger connected to a Code node that returns a static JSON object with a 'result' field set to 42.",
        "gold_fix": """{
  "name": "Static result",
  "nodes": [
    {"id": "1", "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "position": [0, 0], "parameters": {}},
    {"id": "2", "name": "Code", "type": "n8n-nodes-base.code", "position": [200, 0], "parameters": {"jsCode": "return [{ json: { result: 42 } }];"}}
  ],
  "connections": {"Manual Trigger": {"main": [[{"node": "Code", "type": "main", "index": 0}]]}}
}""",
    },
    {
        "domain": "n8n",
        "task_type": "fix_generation",
        "query": "Write an n8n workflow JSON with a Webhook Trigger connected to a Respond to Webhook node that returns a 200 with a static JSON body.",
        "gold_fix": """{
  "name": "Simple webhook responder",
  "nodes": [
    {"id": "1", "name": "Webhook Trigger", "type": "n8n-nodes-base.webhook", "position": [0, 0], "parameters": {"path": "ping", "httpMethod": "GET"}},
    {"id": "2", "name": "Respond to Webhook", "type": "n8n-nodes-base.respondToWebhook", "position": [200, 0], "parameters": {"respondWith": "json", "responseBody": "{\\"status\\": \\"ok\\"}"}}
  ],
  "connections": {"Webhook Trigger": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]}}
}""",
    },
    {
        "domain": "github_actions",
        "task_type": "fix_generation",
        "query": "Write a GitHub Actions job named 'release' that runs only on tags matching v*, checks out the repo, and creates a GitHub release using softprops/action-gh-release.",
        "gold_fix": """name: Release
on:
  push:
    tags:
      - "v*"
jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: softprops/action-gh-release@v2
""",
    },
]
