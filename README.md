# pipen-mcp

A [pipen](https://github.com/pwwang/pipen) CLI plugin that exposes pipen processes and pipelines as [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) tools, allowing AI assistants to discover and run bioinformatics pipelines.

## Overview

`pipen-mcp` bridges pipen's process/pipeline ecosystem with AI assistants that support the Model Context Protocol. Once installed, any namespace registered via the `pipen_cli_run` entry point group is automatically discoverable and executable by an MCP-compatible client (e.g., Claude, VS Code Copilot, Cursor).

## Installation

```bash
pip install pipen-mcp
```

`pipen-mcp` requires Python ≥ 3.10 and depends on:
- [`pipen-cli-run`](https://github.com/pwwang/pipen-cli-run) ≥ 1.0.1
- [`pipen-annotate`](https://github.com/pwwang/pipen-annotate) ≥ 1.0
- [`mcp[cli]`](https://github.com/modelcontextprotocol/python-sdk) ≥ 2.0

## Usage

`pipen-mcp` adds an `mcp` subcommand to the `pipen` CLI:

```
pipen mcp [--transport {stdio,sse,streamable-http}] [--host HOST] [--port PORT]
```

| Option | Description | Default |
|---|---|---|
| `--transport` | MCP transport (`stdio`, `sse`, or `streamable-http`) | `stdio` |
| `--host` | Host to bind to (SSE / streamable-http only) | `127.0.0.1` |
| `--port` | Port to listen on (SSE / streamable-http only) | `8520` |

### stdio (default)

Suitable for direct integration with MCP clients that launch the server as a subprocess:

```bash
pipen mcp
```

### SSE

Starts an HTTP server with Server-Sent Events transport:

```bash
pipen mcp --transport sse --host 0.0.0.0 --port 8520
```

### Streamable HTTP

Starts an HTTP server with the streamable-HTTP transport:

```bash
pipen mcp --transport streamable-http --host 0.0.0.0 --port 8520
```

## MCP Tools

The server exposes four tools that support a progressive-disclosure workflow:

| Tool | Description |
|---|---|
| `get_namespaces` | List all available namespaces. Start here to discover what is installed. |
| `get_processes` | List all processes/pipelines available in a namespace. |
| `get_process` | Get the full argument schema for a specific process/pipeline. |
| `run_process` | Execute a process/pipeline with a list of CLI arguments. |

### Typical workflow

```
1. get_namespaces()
   → "delim", "bam", "rnaseq", ...

2. get_processes("delim")
   → RowsBinder (proc): Bind rows of input files
   → ColsBinder (proc): Bind columns of input files

3. get_process("delim", "RowsBinder")
   → Required:
       --in.infiles <list[str]>  Input files
   → Optional:
       --envs.sep <str> (default: '\t')  Separator
       --outdir <str>  Output directory
       ...

4. run_process("delim", "RowsBinder", [
       "--in.infiles", "/tmp/a.csv,/tmp/b.csv",
       "--envs.sep", ",",
       "--outdir", "/tmp/out"
   ])
   → Pipeline output / logs
```

## VS Code / Copilot Integration

Add the server to your MCP configuration (`~/.vscode/mcp.json` or `~/.vscode-server/data/User/mcp.json`):

```json
{
  "servers": {
    "pipen-mcp": {
      "type": "stdio",
      "command": "pipen",
      "args": ["mcp"]
    }
  }
}
```

Or for SSE:

```json
{
  "servers": {
    "pipen-mcp": {
      "type": "sse",
      "url": "http://127.0.0.1:8520/sse"
    }
  }
}
```

## Authoring a Namespace

Any package can register processes/pipelines with `pipen-mcp` by declaring a `pipen_cli_run` entry point:

```toml
# pyproject.toml
[project.entry-points."pipen_cli_run"]
myns = "mypackage.ns.myns"
```

The referenced module should contain `Proc` subclasses (with an `input` attribute) or `ProcGroup` subclasses. Use [`pipen-annotate`](https://github.com/pwwang/pipen-annotate) to document arguments — annotated fields are exposed in `get_process` output and used to build the tool schema.

```python
# mypackage/ns/myns.py
"""My namespace — tools for processing text files."""
from pipen import Proc
from pipen_annotate import annotate

@annotate
class MyProc(Proc):
    """Concatenate rows from multiple files.

    Input:
        infiles (list): Input files to concatenate

    Envs:
        sep (str): Column separator. Default: ","
    """
    input = "infiles:files"
    output = "outfile:file:{{in.infiles[0] | stem}}_concat.tsv"
    script = "..."
```

## License

MIT
