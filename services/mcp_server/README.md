# HSAAI MCP Server (v3.0)

Model Context Protocol (MCP) server — exposes HSAAI tools and resources to external AI clients.

## Supported Clients

- **Claude Desktop** — add to `claude_desktop_config.json`
- **Cursor** — configure in Settings → MCP
- **Cline** — configure in `cline_config.json`
- **Any MCP-compatible client**

## Configuration (Claude Desktop Example)

```json
{
  "mcpServers": {
    "hsaai": {
      "url": "http://localhost:8094/mcp",
      "headers": {
        "Authorization": "Bearer <your-jwt-token>"
      }
    }
  }
}
```

## Exposed Tools

| Tool | Description |
|------|-------------|
| `hsaai_knowledge_search` | Search enterprise knowledge base (RAG) |
| `hsaai_ask_agent` | Ask a department agent (HR/Finance/IT/Legal/Executive) |
| `hsaai_llm_generate` | Generate text via local LLM (qwen3:8b) |
| `hsaai_workflow_start` | Start a workflow (purchase, leave, ticket) |
| `hsaai_compliance_report` | Generate SOX/GDPR/NDMO/PDPL report |

## Exposed Resources

| URI | Description |
|-----|-------------|
| `hsaai://knowledge/stats` | Knowledge base statistics |
| `hsaai://agents/list` | Available department agents |
| `hsaai://workflow/templates` | Workflow templates |
| `hsaai://models/list` | Available LLM models |

## Deployment

```bash
docker build -t hsaai/mcp-server:3.0.0 services/mcp_server/
docker run -d -p 8094:8094 --name hsaai-mcp-server hsaai/mcp-server:3.0.0
```
