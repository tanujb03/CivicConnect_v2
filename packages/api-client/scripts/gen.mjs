// Regenerates src/schema.d.ts from backend/openapi.json and records the SHA-256 of the spec in src/schema.sha256.
// backend/tests/test_api_client_generated.py recomputes that hash in Python and fails when openapi.json changed without a regeneration.
// Run from the repo root with:  scripts/dev/gen_api_client.ps1   (it first runs `python -m backend.scripts.generate_openapi`)
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const pkg = join(here, "..");
const spec = join(pkg, "..", "..", "backend", "openapi.json");
const out = join(pkg, "src", "schema.d.ts");
const bin = join(pkg, "node_modules", "openapi-typescript", "bin", "cli.js");

const run = spawnSync(process.execPath, [bin, spec, "-o", out], { stdio: "inherit", cwd: pkg });
if (run.status !== 0) process.exit(run.status ?? 1);

// the hash is over the spec text with line endings normalised to LF (the same rule as the Python test)
const text = readFileSync(spec, "utf8").replace(/\r\n/g, "\n");
writeFileSync(join(pkg, "src", "schema.sha256"), createHash("sha256").update(text, "utf8").digest("hex") + "\n");
console.log("schema.d.ts and schema.sha256 written");
