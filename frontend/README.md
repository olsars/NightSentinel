# NightSentinel Frontend

A React + Vite tactical security dashboard for the NightSentinel API.

## Requirements

- Node.js 18 or newer
- NightSentinel FastAPI backend running and reachable from the browser

## Setup

1. Copy this `frontend` folder into the NightSentinel repository.
2. In this folder, install dependencies:

   ```bash
   npm install
   ```

3. Copy `.env.example` to `.env` and set the API address:

   ```env
   VITE_API_BASE_URL=http://127.0.0.1:8000
   ```

   If the backend runs on another machine, use that machine's reachable LAN address, for example `http://192.168.1.50:8000`.

4. Start the frontend:

   ```bash
   npm run dev
   ```

5. Open [http://localhost:5173](http://localhost:5173).

## API behavior

The dashboard uses only the existing API contract:

- `GET /health` checks backend connectivity.
- `GET /events` retrieves the newest events (the API's maximum of 100).
- Events refresh every 5 seconds; health checks refresh every 15 seconds.

The event counts and priority breakdown are calculated locally from the returned event array. No unsupported backend endpoints, authentication, camera streams, sensor readings, acknowledgements, or WebSockets are assumed.

## Notes

- Vite is configured to use port `5173`, which is already allowed by the backend's CORS configuration.
- The API base URL is configured through `VITE_API_BASE_URL`.
- If the browser reports a network/CORS error, verify the backend is running, the API URL is reachable from the browser, and the frontend origin is allowed by the backend.
