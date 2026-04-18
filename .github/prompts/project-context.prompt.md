---
description: "Project context for pipen-mcp. Load this before continuing work on the project to understand what was built, key decisions, gotchas, and what remains."
name: "pipen-mcp context"
agent: "agent"
---

# pipen-mcp — Project Context

## What this project is

`pipen-mcp` exposes pipen `Proc` and `ProcGroup` classes as **MCP tools**, so
LLM clients (Claude Desktop, MCP Inspector, etc.) can run pipen pipelines via
the Model Context Protocol.

It is a pipen CLI plugin — invoked as `pipen mcp` — using the same architecture
as [`pipen-cli-run`](https://github.com/pwwang/pipen-cli-run) (`pipen run`).

## Repository layout

```
pipen_mcp/
  __init__.py       exports PipenMcpPlugin
  version.py        __version__ = "0.0.1"
  entry.py          PipenMcpPlugin(AsyncCLIPlugin) — CLI entry, transport dispatch
  introspect.py     get_proc_schema() / get_group_schema() — static class introspection
  server.py         build_server(entry_points) → FastMCP — tool factory
tests/
  utils.py          plugin_to_entrypoint() helper (same pattern as pipen-cli-run)
  example_procs.py  copied from pipen-cli-run tests — Proc test fixtures
  example_pipeline.py  copied from pipen-cli-run tests — ProcGroup test fixtures
  test_mcp.py       11 tests, all passing
.github/
  prompts/
    debug-pipen-plugin.prompt.md   prompt for debugging runtime errors
pyproject.toml      Python >=3.10, deps: pipen-cli-run, pipen-annotate, mcp[cli]
```

## Key design decisions

### Entry point reuse
`pipen-mcp` reads the **same** `pipen_cli_run` entry point group (`ENTRY_POINT_GROUP =
"pipen_cli_run"` imported from `pipen_cli_run.entry`). Third-party packages register
namespaces once in `pyproject.toml`:

```toml
[project.entry-points."pipen_cli_run"]
mynamespace = "mypackage.procs"
```

Both `pipen run` and `pipen mcp` then discover and expose those namespaces.

### Eligibility rules (identical to pipen-cli-run)
- **Proc**: `issubclass(attrval, Proc) and attrval.input` — must have inputs defined
- **ProcGroup**: `issubclass(attrval, ProcGroup) and attrval is not ProcGroup and attrval is
  not ArgsProcGroup`
- Non-type attributes in namespace modules are silently skipped

### Schema introspection (no subprocess!)
Schemas are derived by **direct class attribute inspection**, not by running a subprocess:
- `pipen_annotate.annotate(proc_cls).Input` → input channel help text
- `proc.input` string parsed (comma-split, `name:type`) → one required field per channel
- `pipen_annotate.annotate(group_cls).Args` → ProcGroup typed args and help
- `ProcGroup.DEFAULTS` → default values
- Standard pipen params (`--outdir`, `--forks`, `--scheduler`, `--profile`, `--cache`)
  always appended

The `FieldDef` dataclass in `introspect.py` carries: `name` (Python identifier),
`cli_arg` (e.g. `--in.infile`), `type_`, `default`, `description`.

### CLI arg mapping
| Source | CLI flag passed to `pipen run` |
|--------|-------------------------------|
| Proc input channel `infile` | `--in.infile` (auto-flattened for single-proc) |
| ProcGroup arg `input` in `ExampleProcGroup` | `--ExampleProcGroup.input` |
| Standard params | `--outdir`, `--forks`, etc. |

### Dynamic FastMCP tool registration
`server.py` uses `mcp.add_tool(handler, name=..., description=...)` in a loop.
Tool names: `{namespace}__{pipen_name}` with hyphens/dots replaced by underscores.

Each handler's **`__signature__`** is overridden with `inspect.Signature` +
`Annotated[T, Field(description=...)]` so FastMCP generates a correct, typed JSON
schema per tool without needing Pydantic model classes.

### Tool handler execution
Each tool is `async def` and calls:
```python
proc = await asyncio.create_subprocess_exec(
    "pipen", "run", ns, proc_name, *cli_args,
    stdout=PIPE, stderr=PIPE,
)
stdout, stderr = await proc.communicate()
```
`pipen run` uses `prefix_chars="+"` internally so that all `--key val` args passed
after the proc name are collected as positionals and forwarded to `pipen_args.parser`
via `set_cli_args()`. The MCP handler just builds standard `--key val` list items.

### Transport dispatch (entry.py)
The installed `mcp` 1.x `FastMCP` does **not** have a unified `run_async(transport=)`
method. The correct per-transport async methods are:
```python
await server.run_stdio_async()
await server.run_sse_async(host=..., port=...)
await server.run_streamable_http_async(host=..., port=...)
```

### Testing
- All tests use `@pytest.mark.forked` — pipen and pipen-args use global singletons
  (`ParserMeta._INST`) that would contaminate between tests without process isolation
- `plugin_to_entrypoint(module)` wraps a module as a fake `EntryPoint`-like object
  (with `load()` returning the module) without triggering the real entry point scanning
- `patch_init` fixture monkey-patches `PipenMcpPlugin.__init__` to inject test namespaces

## What the `+` prefix is (common confusion point)
`pipen-cli-run` uses `prefix_chars="+"` for the sub-subparser (proc/group level).
This means `-` is **not** treated as a flag character, so `--outdir ./out --forks 4`
are all treated as positionals, collected into `pipeline_args: list[str]`, and then
passed to pipen-args via `parser.set_cli_args(pipeline_args)`. **Users never type `+`**;
it is purely an argparse trick to let two parsers coexist without interference.

## Installed versions (as of implementation)
```
pipen          1.1.14
pipen-cli-run  1.0.4
pipen-args     1.2.x
pipen-annotate 1.x
mcp            1.x   (FastMCP from mcp.server.fastmcp)
```

## Current test status
```
11 passed in ~9s
```

## Known issues / things to watch
1. **`FastMCP.run_async` does not exist** in mcp 1.x — use the per-transport methods
   (already fixed in `entry.py`)
2. **`list` fields in handlers** — expanded as separate positional values after the flag:
   `["--ExampleProcGroup.input", "a", "b", "c"]` — not `--flag a,b,c`
3. **`type(epoint).__name__ == "EntryPoint"`** — intentional, not `isinstance()`, to avoid
   import cycles. Do not refactor this check.
4. Coverage is low for `introspect.py` and `server.py` — those modules are tested
   indirectly via the unit tests but not via CLI integration tests. Adding integration
   tests that actually run `pipen mcp` end-to-end is a good next step.

## Potential next steps
- Integration test: start `pipen mcp` with stdio transport, connect with MCP client,
  verify tool list matches installed namespaces
- Support `pipeline_args: list[str] | None` escape hatch for advanced users to pass raw
  pipen-args flags not in the schema
- Streaming output via `mcp.server.fastmcp.Context` to surface live pipen logs to the
  LLM during long pipeline runs
- GitHub Actions CI workflow (copy from pipen-cli-run's `.github/workflows/build.yml`)
- Publish to PyPI once stable
