<#
.SYNOPSIS
  Regenerates packages/api-client from the backend's OpenAPI spec: python -m backend.scripts.generate_openapi, then openapi-typescript, then the typecheck and the client tests.
.DESCRIPTION
  Run from the repo root after any API change. It rewrites backend/openapi.json, packages/api-client/src/schema.d.ts and src/schema.sha256 (commit all three). A Python test
  (backend/tests/test_api_client_generated.py) fails when the spec changed and these were not regenerated. npm's cache and the install stay on D: (C: is nearly full).
#>
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root
$env:TEMP = "D:\ml-cache\tmp"; $env:TMP = "D:\ml-cache\tmp"
& "$root\.venv\Scripts\python.exe" -m backend.scripts.generate_openapi
if ($LASTEXITCODE -ne 0) { throw "generate_openapi failed" }
Set-Location "$root\packages\api-client"
if (-not (Test-Path "node_modules")) { npm install --cache D:\ml-cache\npm --no-audit --no-fund; if ($LASTEXITCODE -ne 0) { throw "npm install failed" } }
npm run gen;       if ($LASTEXITCODE -ne 0) { throw "generation failed" }
npm run typecheck; if ($LASTEXITCODE -ne 0) { throw "typecheck failed" }
npm test;          if ($LASTEXITCODE -ne 0) { throw "client tests failed" }
Write-Host "packages/api-client is current. Commit backend/openapi.json and packages/api-client/src/schema.*"
