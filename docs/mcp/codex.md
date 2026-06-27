# Codex MCP setup

This is the verified Codex configuration for the GitHub Tags Finder MCP server.

Replace `/absolute/path/to/github-tags-finder` below with the absolute path to
this repository. Add the configuration to `~/.codex/config.toml`, or to
`.codex/config.toml` in a trusted project:

```toml
[mcp_servers.github_tags]
command = "uv"
args = [
  "--directory",
  "/absolute/path/to/github-tags-finder",
  "run",
  "--extra",
  "mcp",
  "github-tags-mcp",
]
startup_timeout_sec = 20
tool_timeout_sec = 60
```

The server loads GitHub credentials from the repository's ignored `.env` file.
If the credentials are exported in the environment instead, add this setting:

```toml
env_vars = ["GITHUB_TOKEN", "GH_TOKEN", "GITHUB_API_URL"]
```

Restart Codex after changing its configuration, then use `/mcp` to confirm that
the `github_tags` server and `search_github_issues` tool are available.

See the [general MCP guide](mcp.md) for installation, authentication, tool
behavior, and transport details.
