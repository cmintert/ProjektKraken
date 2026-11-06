"""Build local-only client artifacts from an already built Windows package."""

import argparse
import json
import shutil
import zipfile
from pathlib import Path


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def package_clients(package: Path, output: Path) -> None:
    """Create self-contained client bundles without modifying installed clients."""
    connector = package / "KrakenMCP.exe"
    runtime = package / "_internal"
    if not connector.is_file() or not runtime.is_dir():
        raise ValueError("Build the Windows package and its KrakenMCP.exe first")
    output.mkdir(parents=True, exist_ok=True)
    for client in ("chatgpt", "claude"):
        destination = output / client
        destination.mkdir()  # Never overwrite an earlier reviewed artifact.
        shutil.copy2(connector, destination / connector.name)
        shutil.copytree(runtime, destination / "_internal")
        if client == "chatgpt":
            _json(
                destination / "plugin.json",
                {
                    "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                    "name": "projektkraken",
                    "version": "0.1.0",
                    "description": "Read saved Kraken world facts during explicit sharing.",
                    "license": "GPL-3.0-only",
                    "extensions": {"com.openai": {"requires_local_executor": True}},
                },
            )
            _json(
                destination / "mcp.json",
                {
                    "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                    "mcpServers": {
                        "projektkraken": {
                            "type": "stdio",
                            "command": "${PLUGIN_ROOT}/KrakenMCP.exe",
                            "args": [],
                            "cwd": "${PLUGIN_ROOT}",
                        }
                    },
                },
            )
        else:
            _json(
                destination / "manifest.json",
                {
                    "manifest_version": "0.3",
                    "name": "projektkraken",
                    "version": "0.1.0",
                    "author": {"name": "ProjektKraken"},
                    "description": "Read saved Kraken world facts during explicit sharing.",
                    "compatibility": {"platforms": ["win32"]},
                    "server": {
                        "type": "binary",
                        "entry_point": "KrakenMCP.exe",
                        "mcp_config": {
                            "command": "${__dirname}/KrakenMCP.exe",
                            "args": [],
                        },
                    },
                },
            )
        (destination / "README.md").write_text(
            "# Kraken local connector\n\n"
            "Open Kraken and enable Settings > Integrations > Local AI access (MCP). "
            "Installing this package never enables sharing. Stop sharing in Kraken "
            "to revoke access. Returned lore may be sent to your AI provider. "
            "ChatGPT compatibility requires a verified locally executing Desktop "
            "chat; no cloud/tunnel substitute is provided.\n",
            encoding="utf-8",
        )
        shutil.copy2(
            Path(__file__).resolve().parents[1] / "LICENSE", destination / "LICENSE"
        )
        suffix = ".zip" if client == "chatgpt" else ".mcpb"
        with zipfile.ZipFile(
            output / (client + suffix), "x", zipfile.ZIP_DEFLATED
        ) as bundle:
            for file in sorted(destination.rglob("*")):
                if file.is_file():
                    bundle.write(file, file.relative_to(destination).as_posix())
        with zipfile.ZipFile(output / (client + suffix)) as bundle:
            if bundle.testzip() is not None or "KrakenMCP.exe" not in bundle.namelist():
                raise ValueError("Client artifact verification failed")
    _json(
        output / "codex-config.json",
        {
            "command": str(connector.resolve()),
            "args": [],
            "note": "Use this command as mcp_servers.projektkraken.command in config.toml",
        },
    )


def main() -> None:
    """Parse explicit artifact locations; no upload or installation side effects."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    package_clients(arguments.package, arguments.output)


if __name__ == "__main__":
    main()
