# Frontend (Story 9)

React + TypeScript + Vite shell for OpenClaw Monitor UI.

## Setup
```bash
cd frontend
npm install
```

## Run Locally
```bash
cd frontend
npm run dev
```

By default, Vite proxies `/api/*` to `http://127.0.0.1:8000`.

To override backend target during local dev:

```bash
VITE_DEV_PROXY_TARGET=http://127.0.0.1:8000 npm run dev
```

To hardcode an absolute API base URL in the app bundle, set:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Build
```bash
cd frontend
npm run build
```

## Test
```bash
cd frontend
npm test
```
