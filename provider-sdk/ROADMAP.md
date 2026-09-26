# Roadmap

The order below is deliberately conservative: stabilize the provider boundary before expanding the catalog surface.

## 0.2 — executable reference provider host

- JSON-RPC subprocess runner reference implementation;
- request timeout/cancellation model;
- structured stderr diagnostics;
- provider health/restart behavior;
- cross-platform executable selection from `.mdxprovider` bundles.

## 0.3 — Provider Bridge reference server

- authenticated HTTPS/LAN bridge;
- short-lived pairing flow;
- device revocation;
- bridge discovery and QR pairing metadata;
- redacted diagnostics.

## 0.4 — richer catalog

- browse/navigation nodes;
- album tracks and artist releases;
- library add/remove;
- recommendation seeds;
- capability negotiation for optional methods.

## 0.5 — trust and signing

- bundle digest format;
- publisher signatures;
- verified-publisher keyring format;
- reproducible packaging guidance.

## 1.0 — compatibility commitment

- frozen core method names and required fields;
- explicit deprecation rules;
- compatibility test suite;
- protocol conformance badges for provider repositories.
