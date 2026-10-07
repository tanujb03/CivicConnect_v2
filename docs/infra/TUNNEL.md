# Reaching the API from a phone (Expo app)

A phone cannot use `localhost`, and the evidence upload and download links the API hands out are absolute URLs. They are built from `PUBLIC_BASE_URL` (default `http://localhost:8000`, `backend/core/config.py`, used by `LocalStorage` in `backend/storage.py`), so that setting must be an address the **phone** can reach, and the app's API base URL must point at the same address. Two ways:

## A. Same Wi-Fi (no extra software)

1. Find the laptop's Wi-Fi address (`ipconfig`, the `Wi-Fi` adapter, IPv4; on 2026-10-04 it was 192.168.1.41, it changes with the network).
2. Start the API with that address in the setting and listening on all interfaces:
   ```powershell
   $env:PUBLIC_BASE_URL = "http://192.168.1.41:8000"      # a lane: its port, 8000 + slot
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```
   Compose: `$env:PUBLIC_BASE_URL = "http://192.168.1.41:8000"` before `docker compose ... up -d` (the compose backend already listens on all interfaces; see `docs/infra/COMPOSE.md`).
3. Windows Defender Firewall must allow inbound TCP on that port for the **Private** network profile, and the phone must be on the same network (guest Wi-Fi and some university networks isolate clients).

Verified on the laptop: with `PUBLIC_BASE_URL=http://192.168.1.41:8002` the compose backend returned upload and download URLs starting with that address, and the PUT, complete and GET steps worked through it. Not verified: access from a real phone, and whether the firewall lets other devices in.

## B. Cloudflare quick tunnel (any network, HTTPS, no account)

1. Install once: `winget install --id Cloudflare.cloudflared` (open a new terminal afterwards so `cloudflared` is on the PATH).
2. Start the API on port 8000 (or the lane's port) as usual, then in a second terminal:
   ```powershell
   cloudflared tunnel --url http://localhost:8000
   ```
   It prints a line like `https://<random-words>.trycloudflare.com`. That is the public address of your API.
3. Stop the API, set the address and start it again (the URL is baked into the signed links when they are created, so the API must be restarted with it):
   ```powershell
   $env:PUBLIC_BASE_URL = "https://<random-words>.trycloudflare.com"
   python -m uvicorn backend.main:app --port 8000
   ```
   Put the same address into the phone app as its API base URL.
4. Check from the phone's browser: `https://<random-words>.trycloudflare.com/api/v1/health/ready` must answer `"status":"ready"`.

Things to know:
* The address changes every time `cloudflared` restarts, so steps 3 and 4 repeat (and the app's API base URL changes with them). A quick tunnel is for demos and testing; Cloudflare gives no uptime guarantee for it.
* The API becomes reachable from the whole internet while the tunnel runs. A database seeded with `seed_demo` has known accounts and one shared password (`civicconnect-demo`): use `--reference-only` or keep the tunnel short, and never tunnel a database with real citizen data from a development machine.
* Uploads go through the tunnel too, so large files are slower than on the LAN; `MAX_UPLOAD_BYTES` (25 MB) still applies.
* The native Expo app needs no CORS entry. A browser app on another origin (Expo web, a Vite dev server) does: add that origin to `CORS_ORIGINS`.
* With `STORAGE_BACKEND=s3` the signed links point at `S3_ENDPOINT_URL`, not at `PUBLIC_BASE_URL`; that address must be reachable from the phone as well.

Not verified: everything in this section B. `winget` was not available in the session that wrote this and `cloudflared` is not installed on the laptop, so the install command, the printed URL format and the phone round trip are written from Cloudflare's documented behaviour and have not been run here.
