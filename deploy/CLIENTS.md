# Connecting Claude clients to a remote ndcourts-mcp

The server (see [SETUP.md](SETUP.md)) speaks Streamable HTTP behind
TLS + HTTP Basic Auth. You'll need from the admin:

- **URL** — `https://mcp.example.com/mcp`
- **Username** — assigned to you
- **Password** — shared via a secure channel

## Compatibility

| Client | Supported | How |
|---|---|---|
| Claude Code (CLI, any OS) | yes | `claude mcp add --transport http` |
| Claude Desktop (macOS, Linux, Windows) | yes | `mcp-remote` stdio→HTTP bridge |
| claude.ai web | no | requires OAuth, not Basic Auth |
| Claude iOS / iPad / Android | no | same as web |

The web/mobile clients use Anthropic's Custom Connectors, which speak
MCP-over-OAuth. This server uses Basic Auth, so those clients can't
talk to it today. Adding OAuth is a future-work item.

---

## Claude Code (CLI)

One command — replace the placeholders:

```bash
claude mcp add --transport http ndcourts https://mcp.example.com/mcp \
  --header "Authorization: Basic $(printf '<username>:<password>' | base64)"
```

The base64 is computed locally before being saved. Verify with
`claude mcp list`. Tools appear as `mcp__ndcourts__*` after a session
restart.

**Project-scoped alternative.** If a repo's collaborators should all
use this MCP, add it to a project's `.mcp.json` instead of the user-
level config:

```json
{
  "mcpServers": {
    "ndcourts": {
      "type": "http",
      "url": "https://mcp.example.com/mcp",
      "headers": {
        "Authorization": "Basic <base64-of-user:pass>"
      }
    }
  }
}
```

⚠ Don't commit `.mcp.json` with real credentials. Either commit a
template and have each user add their own header locally, or keep the
file untracked.

---

## Claude Desktop — macOS and Linux

Claude Desktop's MCP loader only accepts **stdio** servers, so we
proxy through `mcp-remote` (an npx package that runs locally and
forwards to the HTTP endpoint).

**Prerequisites:** Node.js. Confirm with `node --version`; install via
`brew install node` on macOS or your package manager on Linux.

**Config file:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

Open it via Settings → Developer → **Edit Config**, or edit directly.
Add the following inside `mcpServers` (preserve anything already there):

```json
"ndcourts": {
  "command": "npx",
  "args": [
    "-y",
    "mcp-remote",
    "https://mcp.example.com/mcp",
    "--header",
    "Authorization: Basic <base64-of-user:pass>"
  ]
}
```

Generate the base64 in Terminal:

```bash
printf '<username>:<password>' | base64
```

Save, **⌘Q** Claude Desktop (a window-close isn't enough), reopen.
Settings → Developer → MCP servers should show `ndcourts` connected.

---

## Claude Desktop — Windows

Same approach, different paths.

**Prerequisites:** Node.js. In PowerShell, `node --version`; install
via `winget install OpenJS.NodeJS.LTS` if missing.

**Config file:** `%APPDATA%\Claude\claude_desktop_config.json`. Open
via Settings → Developer → **Edit Config**, or edit directly.

Add the same `ndcourts` block as in the macOS section. To generate
the base64 in PowerShell:

```powershell
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('<username>:<password>'))
```

Save, fully quit Claude Desktop (right-click tray → **Quit**, not just
close the window), reopen.

---

## Troubleshooting

- **"Some MCP servers could not be loaded"** on Desktop start: the
  entry shape is wrong. Use the stdio shape above (`command` + `args`).
  `{"type": "http", ...}` is accepted by Claude Code but rejected by
  Claude Desktop.
- **401 Unauthorized** on first request: bad credentials. The base64
  of `<username>:` (empty password) starts with `dXNlcjo=`-style; a
  real cred is longer. Recompute and replace.
- **Hanging on "Connecting…"** for 30+ seconds on first launch: the
  one-time `npx -y mcp-remote` download. Wait it out. If it persists,
  run the command manually in a terminal to see errors:
  ```bash
  npx -y mcp-remote https://mcp.example.com/mcp --header "Authorization: Basic <base64>"
  ```
- **Reachability check** (any OS): `curl -I https://mcp.example.com/mcp`
  should return `401 Unauthorized` with a `WWW-Authenticate: Basic`
  header. Connection refused or timeout = DNS/networking issue, not
  the MCP config.

---

## Revoking access

The admin removes your line from `/etc/apache2/mcp.htpasswd` on the
server and reloads Apache. Your client will start getting 401s on its
next request; remove the entry from your local config when convenient.
