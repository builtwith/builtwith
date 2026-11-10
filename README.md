<p align=center><img src="https://raw.githubusercontent.com/builtwith/builtwith/main/newLogoSquare.png" width="20%"></p>

# 🚀 BuiltWith Official Repo

## Current API endpoints

Uses Domain v26, Lists v13, Relationships v5, and MCP Registry v2 where supported. Existing unversioned registry methods now use v2; explicit v2 aliases remain available. Registry JSON is an array with per-endpoint tools and discovery `Overview` objects.

Relationships requests return one page (up to 1000 records). Pass `next_page` as `PAGE` while `more_results` is true, keeping the lookup domain and IP option unchanged. `OFFSET` and `SKIP` are not supported. Bulk Domain retains its separate `/v23/domain/bulk` routes.

## Domain API v26

Domain lookups now use API v26. Technology records include numeric `confidence` scores from 0 to 1. Full JSON responses include `Meta.company_reg`, an array of company registration records with string `type` and `number` fields; registration numbers preserve leading zeros. The array is empty when unavailable or metadata is excluded. See the [API reference](https://api.builtwith.com/llms.txt).

> 🌐 Find out what websites are built with at [builtwith.com](https://builtwith.com) — now with extra GitHub flavour! 🎉

## 🛠️ Our Projects

- 🍌 [BuiltWith Pty Ltd](https://github.com/BuiltWith-Pty-Ltd) — the mothership org for enterprise-level GitHub shenanigans
- 🤖 [AI First SDK](https://github.com/builtwith/builtwith-ai-sdk) — for our AI Agent overlords (they asked us to build this)
- 🖥️ [TUI Interface](https://github.com/builtwith/builtwith-tui) — poke the BuiltWith API from your terminal like a pro
- ⌨️ [CLI](https://github.com/builtwith/builtwith-cli) — non-interactive, scriptable CLI for automation, CI/CD pipelines and AI agents (`bw domain lookup shopify.com | jq .`)
- 🧠 [MCP Server](https://github.com/builtwith/builtwith-mcp) — plug BuiltWith straight into your AI tools via Model Context Protocol
- 🐣 [Code Examples](https://github.com/builtwith/builtwith-code-examples) — loads of tasty API usage examples to get you started fast
- 🟨 [Node.js API](https://github.com/builtwith/builtwith-node-api) — a Node wrapper for the BuiltWith API that actually works™
- 🐍 [Python SDK](https://github.com/builtwith/builtwith-python) — typed sync/async client and integration with the existing MCP server (`pip install builtwith-official`)
- 🔷 [C# API](https://github.com/builtwith/builtwith-csharp-api) — .NET / NuGet goodness for the C# crowd
- 📋 [List API Demo](https://github.com/builtwith/listapidemo) — quick demo showing how to use the BuiltWith List API

## Recent API Coverage

The client libraries and examples now include the VAT API at `https://api.builtwith.com/vat1/api.json`, which returns VAT, GST, CNPJ, ABN, and other publicly displayed company registration numbers for 1 to 16 comma-separated domains (`LOOKUP=example.com`). The companion VAT Types API at `https://api.builtwith.com/vat1/types.json` lists every registration type it can return — no API key required.

## 📬 Postman contracts and release checks

The [Postman workspace](https://www.postman.com/builtwithcom/builtwith) has 33 emoji collections and four specifications. Their canonical public files live in [`postman/`](postman/): REST, x402 pay-per-call, Stripe credit top-up, and the live feed. REST models use reviewed server serialization and the maintained C# models, with synthetic examples for pagination, nullable values, confidence scores, and registration numbers. Financial/social payloads and remote MCP discovery extensions remain open where their fields vary.

Install `postman/requirements.txt`, then run `python -m unittest discover -s postman/tests` and `python postman/scripts/manage.py check --online`. Checks validate the schemas, examples, collection URLs, credential placeholders, current public endpoint versions, and the published payment specs. They make no authenticated BuiltWith lookups and consume no API credits.

Changes on `main` and a weekly scheduled check validate then sync the 33 collections and four specs to their existing Postman IDs. Manual runs are available under **Actions → Validate and sync Postman**. Sync reads `POSTMAN_API_KEY` from the repository's Actions secret, updates changed definitions, and verifies each readback. Pull requests validate without that secret. Redirects are refused, remote error bodies are omitted from logs, and populated credentials are rejected before upload. Keep personal keys in local Postman variables; never commit populated environments or captured tokens.

Client release workflows reuse `.github/workflows/postman-contract.yml` to check the selected release source against the current contracts before npm staging. Python and C# run the same check in CI. If a public endpoint version, payment spec, or C# model changes, the check fails for review; it does not guess a migration. Update the collections and reviewed declarations in `postman/contracts/`, run `python postman/scripts/refine_spec.py`, validate, and commit the result. The sync uses these committed definitions as the source of truth, so mirror intentional Postman UI edits here before the next sync. The `third_party/postman` working folder is an export copy, not the automation source.

## 🔗 More Useful Stuff

- 🍕 Explore all the [BuiltWith APIs](https://api.builtwith.com) — there's a lot more than you think!
- 📬 The [Postman workspace](https://www.postman.com/builtwithcom/workspace/builtwith/overview) is super handy for testing API calls IMHO
- 💬 [Contact us](https://builtwith.com/contact) if something's broken, weird, or you just want to say hi 👋


