# Connect the MCP server to the Claude desktop app

About five minutes. The desktop app starts local MCP servers itself, so the repo has to be on the same computer as the app.

## 1. Get the repo and check it runs

```bash
git clone https://github.com/mtomar01/property-match-agent.git
cd property-match-agent
uv sync
uv run pytest                          # should end with "passed"
uv run python -m evals.harness.run     # should end with "Hard limit breaks: 0"
```

Then find two absolute paths you'll need:

```bash
which uv      # macOS, for example /Users/mike/.local/bin/uv  (Windows: where uv)
pwd           # the repo folder, for example /Users/mike/code/property-match-agent
```

The desktop app starts servers with a minimal `PATH`, so it may not find `uv` unless you give its full path.

## 2. Add the server to the config

In the Claude desktop app, open **Settings** from the Claude menu in the menu bar (not the settings inside the chat window), go to **Developer** and click **Edit Config**. That opens `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add this, with your two paths. If the file already has an `mcpServers` block, add `property_tools` inside it rather than replacing the others.

```json
{
  "mcpServers": {
    "property_tools": {
      "command": "/Users/mike/.local/bin/uv",
      "args": [
        "--directory", "/Users/mike/code/property-match-agent",
        "run", "python", "-m", "mcp_server.server"
      ]
    }
  }
}
```

`--directory` tells uv to run inside the repo, so the server finds its code and the synthetic listings without any other paths.

## 3. Restart and try it

Quit the desktop app completely (not just close the window) and open it again. `property_tools` should appear under connectors. Then ask:

> Find me a two bedroom flat in Egaleo under €200k

Claude should call `search_listings`. Every result is synthetic (their links use the reserved `synthetic.invalid` domain), and every one respects the budget, because the server filters before Claude sees anything.

Good follow-ups to show in a demo:

- "Show me the full details of the first one" calls `get_listing`.
- "Same search, but no basements or semi-basements" tests floor exclusions.
- "Why didn't you show more?" makes Claude read `excluded_because_unknown`, the listings left out because they don't state a price, size, bedrooms or floor.
- "Around 200k, ideally 2 bedrooms" shows the server's own rules: `search_listings` returns the limits it applied (€180k to €220k, 1 to 3 bedrooms).
- "What if I drop the size limit?" calls `check_supply`, which counts in code what each limit costs.
- "Show me the next five as swipe cards" calls `next_cards`: each card carries two reasons taken from its fields, and one card in five is an explore card from outside the top.
- "I like the second one, reject the third, too dark" calls `record_swipe` twice; swipes are kept on your machine only, in `data/private/swipes/`.
- After ten or so, "what do my swipes say?" calls `swipe_patterns`: code compares likes with rejects and returns the clearest pattern with its counts, for Claude to put to you. Change the card only on your yes.
- Pick **criteria_interview** from the prompts menu to have Claude interview you the way the evals measured it; it now ends in the deck tools rather than a table.
- `extract_listing` reads a pasted Greek description into fields; it needs the API key on your machine (one Haiku call, about a tenth of a cent).

## 4. Optional: your real listings, on your own machine only

The real Spitogatos snapshot is private and never goes in the repo. If you copy it to your machine, point the server at it with an `env` block:

```json
"property_tools": {
  "command": "/Users/mike/.local/bin/uv",
  "args": ["--directory", "/Users/mike/code/property-match-agent", "run", "python", "-m", "mcp_server.server"],
  "env": { "PM_SNAPSHOT": "/Users/mike/code/property-match-agent/data/private/snapshot.jsonl" }
}
```

Results then say `"data": "private personal-use snapshot"`.

## If it doesn't connect

- Run the command from step 1 by hand: `uv --directory <repo> run python -m mcp_server.server`. It should sit waiting without errors (press Ctrl+C to stop).
- Logs: `~/Library/Logs/Claude/mcp-server-property_tools.log` on macOS, `%APPDATA%\Claude\logs` on Windows.
- Check the JSON is valid and both paths are absolute.

Sources: [Connect to local MCP servers (modelcontextprotocol.io)](https://modelcontextprotocol.io/docs/2026-07-28/develop/connect-local-servers), [MCP Python SDK: connect to a real host](https://py.sdk.modelcontextprotocol.io/get-started/real-host/), [Getting started with local MCP servers on Claude Desktop](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop).
