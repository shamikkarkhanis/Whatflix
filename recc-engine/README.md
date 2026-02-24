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
