## Recc Engine (uv workflow)

### Setup

```bash
uv sync --extra test --extra dev
```

### Run the API

```bash
make run
```

User profiles are now stored in SQLite at `data/user_profiles.sqlite3`.
To migrate legacy `users/*.json` profiles and remove the JSON files:

```bash
make migrate-users
```

Non-runtime scripts (data fetchers, DB inspectors, API workflow helpers, migrations) live in `helpers/`.

### Docker

1. Create an env file:

```bash
cp .env.example .env
```

2. Start the API container (single replica, stateful):

```bash
make docker-up
```

3. Check health:

```bash
curl http://localhost:8000/
```

State is persisted through bind mounts:
- `data/` (includes `user_profiles.sqlite3`)
- `chroma/` (local Chroma persistence)
- `logs/` (server logs)

Important deployment constraint: this setup is single-replica only because it uses local SQLite and local Chroma storage.

### App Network URL (iOS)

- iOS Simulator on the same Mac: `http://127.0.0.1:8000`
- Physical iPhone on same Wi-Fi: `http://<your-mac-lan-ip>:8000`

Do not use the container IP directly from the app. Use the host machine IP/port mapping.

### Tests

```bash
make test
make test-routes
make test-syntax
```

### Lockfile

```bash
make lock
```
