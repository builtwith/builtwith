# BuiltWith Workspace Agent Notes

Use `CLAUDE.md` first for the project map and release workflow. This file records the repeatable implementation checklist for adding a new BuiltWith API endpoint across the GitHub workspace.

## Endpoint Source

- Prefer the local API docs when provided, especially `https"://api.builtwith.com/llms.txt`.
- Capture the endpoint path, required parameters, optional parameters, response sample, and credit behavior before editing.
- Do not update `listapidemo` unless explicitly asked.

## Project Checklist

- `builtwith-mcp`: add a `registerJsonTool(...)`, update `README.md`, and bump `package.json` plus the MCP server version string.
- `builtwith-ai-sdk/node`: add a `BuiltWithClient` method that calls the MCP tool name, update README method tables, and bump `package.json`.
- `builtwith-ai-sdk/csharp`: add the corresponding `BuiltWithClient` method and update the root SDK README.
- `builtwith-node-api`: add a method to the returned API object using `constructBuiltWithURL(...)`, update README usage, and bump `package.json`.
- `builtwith-cli`: add the base URL, create `lib/commands/<endpoint>.js`, register it in `lib/cli.js`, update README, and bump `package.json`.
- `builtwith-csharp-api`: add async and sync client methods, add typed models under `BuiltWith/Models`, update README, and bump the `.csproj` version.
- `builtwith-tui`: add the endpoint definition to `src/api.js`, update README endpoint counts, and bump `package.json`.
- `builtwith-code-examples`: add `<endpoint>-api/README.md`, `.env.example`, `nodejs/index.js`, optional `nodejs/package.json`, and `python/main.py`.
- `builtwith`: update the top-level README if the endpoint is a broad API coverage change.

## Change API Contract

- Endpoint: `GET https://api.builtwith.com/change1/api.json`
- Required: `KEY`, `LOOKUP`
- Optional: `SINCE`, which accepts natural language dates such as `last month` and defaults to 3 months.
- `LOOKUP` supports comma-separated domains.
- Response shape starts with `Results[]`, each with `Lookup` and `Changes`; `Changes` includes `since_utc`, `last_checked_utc`, `summary`, and `events[]`.

## Verification

- Run JS syntax checks for changed `.js` files with `node --check`.
- Run available package tests where dependencies are already installed.
- Run `dotnet build` for C# projects when the SDK is available.
- Use `--dry-run` for CLI URL checks so API keys and credits are not required.
