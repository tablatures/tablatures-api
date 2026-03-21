# Tablatures API

Flask API backend for the [Tablatures](https://github.com/tablatures/tablatures) guitar tablature web app.

## Features

- **Search**: advanced query parsing (`artist:metallica song:enter`), fuzzy matching with Levenshtein distance, weighted scoring
- **Live multi-source search**: parallel queries to local DB, Songsterr, and Ultimate Guitar with 15-minute cache
- **Autocomplete**: fast prefix-based suggestions for search
- **Download**: streams tab files with SSRF protection and domain whitelisting
- **Catalog**: stats, artist listing, random tabs, recommendations based on favorite artists
- **Metadata**: artist info from MusicBrainz + TheAudioDB, album artwork from iTunes, YouTube video search
- **Rate limiting**: IP-based, configurable via environment variables
- **Compression**: automatic gzip for responses > 500 bytes
- **OpenAPI spec**: available at `/api/docs`

## API Endpoints

All endpoints available under both `/api/` and `/api/v1/` prefixes.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with uptime |
| `/search` | GET | Search tabs (`?q=`, `?artist=`, `?source=`, `?sort=`) |
| `/search/live` | GET | Live multi-source search (`?q=`, `?sources=`) |
| `/autocomplete` | GET | Autocomplete suggestions (`?q=`, `?limit=`) |
| `/download/:tab_id` | GET | Stream tab file |
| `/tab/:tab_id` | GET | Tab metadata preview |
| `/stats` | GET | Database statistics |
| `/artists` | GET | Paginated artist list |
| `/random` | GET | Random tabs for discovery |
| `/recommendations` | GET | Tabs based on favorite artists |
| `/sources` | GET | Available sources with counts |
| `/metadata/artist/:name` | GET | Artist info (image, bio, country, tags) |
| `/metadata/artwork` | GET | Album artwork (`?artist=`, `?title=`) |
| `/youtube/search` | GET | YouTube video search (`?q=`, `?limit=`) |
| `/docs` | GET | OpenAPI specification |

## Data Sources

| Source | Type | Auth |
|--------|------|------|
| Local JSON DB | Tab search & download | None |
| MusicBrainz | Artist metadata (MBID, country, tags) | User-Agent header |
| TheAudioDB | Artist images, bios | Free API key |
| iTunes Search | Album artwork | None |
| YouTube | Video search (scraping) | None |
| Songsterr | Live tab search | None |
| Ultimate Guitar | Live tab search | None |

All external data is cached in-memory for 24 hours.

## Quick Start

```bash
# Setup with Poetry
poetry install --no-root
poetry shell

# Run locally
python -m api.app

# Or with environment variables
PORT=3000 CORS_ORIGINS=http://localhost:5173 python -m api.app
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `3000` | Server port |
| `CORS_ORIGINS` | `*` | Allowed origins (comma-separated) |
| `RATE_LIMIT_MAX` | `100` | Max requests per window |
| `RATE_LIMIT_WINDOW` | `60` | Rate limit window (seconds) |

## Search Features

- **Field-specific**: `artist:metallica album:master song:enter`
- **Fuzzy matching**: `metal enter` matches "Metallica - Enter Sandman"
- **Weighted scoring**: Exact matches (50pts) > Albums (30pts) > Words (10pts)
- **Source filtering**: `source:ultimate-guitar`

## Database Schema

```json
{
  "metadata": { "lastUpdated": "", "totalTabs": 0, "version": "" },
  "tabs": {
    "tab_id": {
      "title": "Enter Sandman",
      "artist": "Metallica",
      "source": "ultimate-guitar",
      "downloadUrl": "https://..."
    }
  },
  "index": {
    "artist": { "metallica": ["tab_id1"] },
    "title": { "enter": ["tab_id1"] },
    "album": { "master": ["tab_id1"] }
  }
}
```

## Deployment

Deployed on **Vercel** as a serverless Python function. Configuration in `vercel.json`.

```bash
# Generate requirements.txt
poetry export -f requirements.txt --output requirements.txt --without-hashes

# Deploy
vercel deploy --prod
```

## Tech Stack

- **Flask 3.1** + Pydantic for type-safe request/response
- **In-memory JSON database** with pre-computed search indexes
- **Requests** for external API calls
- **Poetry** for dependency management
- **Deployed on Vercel** (serverless)

## Performance

- **Cold start**: ~500ms (JSON loaded once)
- **Search latency**: ~50-100ms (in-memory indexes)
- **Memory usage**: ~50MB (cached database)
