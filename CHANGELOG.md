# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project scaffolding: packaging, lint/type/test tooling, docs skeleton.
- Core exception hierarchy, configuration, vector/math/NBT utilities.
- Async event emitter with async handler support and error isolation.
- Protocol stack: packet framing, compression, AES/CFB8 encryption,
  ProtoDef serialization via `protolib`, full state machine
  (handshaking/status/login/configuration/play).
- Authentication: offline mode + Microsoft device-code/OAuth/Xbox Live/XSTS
  flow.
- Vendored minecraft-data for Java 1.21.11 (protocol 774) and version registry.
- `LeafishBot`: connect/spawn/chat/movement/health, entity tracking,
  inventory model, world model, physics engine.
- Fake protocol server + end-to-end integration test.
- `tools/fetch_mcdata.py` for vendoring minecraft-data JSON.
