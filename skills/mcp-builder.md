# Skill: MCP Server Builder

**When to use**: Building a Model Context Protocol (MCP) server to extend Claude with new tools —
e.g. give Claude access to a custom API, database, or service.

## What is MCP

MCP servers expose tools that Claude can call. You build the server, Claude calls it.
Example use case: expose an external API or an internal database as MCP tools.

## 4-phase workflow

### Phase 1 — Research
- What API/service to expose?
- Map endpoints → which become tools vs resources?
- Balance: comprehensive coverage (flexibility) vs workflow tools (specific tasks)

### Phase 2 — Implement (TypeScript recommended)

```bash
npm install @modelcontextprotocol/sdk
```

```typescript
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

const server = new Server({ name: "example-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [{
    name: "get_signal",
    description: "Get the current signal for a ticker",
    inputSchema: {
      type: "object",
      properties: { ticker: { type: "string" }, market: { type: "string", enum: ["US", "CA"] } },
      required: ["ticker"]
    }
  }]
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === "get_signal") {
    const { ticker, market = "US" } = request.params.arguments;
    // ... call your API ...
    return { content: [{ type: "text", text: JSON.stringify(result) }] };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
```

### Phase 3 — Test

```bash
npx @modelcontextprotocol/inspector node dist/index.js
```

### Phase 4 — Evaluate
Write 10 test questions that verify Claude can use the tools correctly.
Questions must be: independent, read-only, have verifiable answers.

## Tool naming rules

- Clear, action-oriented: `get_signal`, `list_tickers`, `search_patterns`
- Consistent prefix by domain: all signal tools start with `signal_`
- Error messages must be actionable: tell Claude exactly what's wrong and how to fix it

## Register in Claude Code settings

```json
{
  "mcpServers": {
    "example": {
      "command": "node",
      "args": ["/path/to/mcp-server/dist/index.js"]
    }
  }
}
```
