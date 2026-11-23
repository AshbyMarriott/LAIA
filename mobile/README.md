# LAIA Mobile

Expo (React Native) client for the self-hosted LAIA assistant. The phone is a thin client: natural language and calendar reads go to your host API over Tailscale or WireGuard.

## Features

- **Setup** — host URL + API key, with connection test (`/healthz` + `/api/health/ollama`)
- **Chat** — `POST /api/assistant/chat` with `conversation_id`, cancelable long requests
- **Pending UI** — confirmation (Yes/No), disambiguation (numbered choices), slot clarification
- **Calendar** — read-only event list/search via `GET /api/events`
- **Settings** — update or clear credentials (secure storage on device)

## Prerequisites

1. LAIA API running and reachable on your Tailscale/WireGuard network
2. Phone and host on the same tailnet (for a physical device)
3. Node.js 20+ and npm
4. **Expo Go from the App Store** (this app targets **Expo SDK 58**, which matches the current store Expo Go)

> The Compose stack may bind the API to `127.0.0.1:8000` on the host. From another device you typically need to publish/bind the API on the Tailscale interface (or use Tailscale Serve / a reverse proxy).
>
> Point the app at whatever URL actually answers `/healthz` from the phone or simulator.
>
> **iOS Simulator:** `http://127.0.0.1:8000` works only if the API runs on the same Mac. For a remote LAIA host, use its Tailscale IP/hostname.

## Run

```bash
cd mobile
npm install
npm start
```

Then open in Expo Go (iOS/Android) or press `w` for web.

```bash
npm run ios      # macOS + Xcode
npm run android  # Android emulator/device
npm run web
```

## Configure in the app

| Field | Value |
|-------|--------|
| Host URL | e.g. `http://100.x.y.z:8000` (Tailscale IP) or your MagicDNS name |
| API key | same as `LAIA_API_KEY` on the host |

Credentials are stored with **expo-secure-store** on iOS/Android (Keychain/Keystore). On web they use `localStorage` (less secure; fine for local dev only).

## Project layout

```text
app/                 Expo Router screens (setup, chat, calendar, settings)
src/api/             Typed HTTP client + error helpers
src/storage/         Secure settings persistence
src/context/         Settings + client provider
src/components/      Chat bubbles, pending actions, event rows
src/theme/           Colors
```

## Notes

- Do **not** put Ollama on the public internet; the phone never talks to Ollama directly.
- Chat latency of several seconds is expected while the local model runs.
- Destructive deletes still require server-side confirmation; the Yes/No buttons send `yes` / `no` as chat messages.
- Voice (STT/TTS) is intentionally out of scope for this client version.
