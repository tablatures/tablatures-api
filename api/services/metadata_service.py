import logging
import time
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# Simple in-memory cache with TTL
_cache: dict = {}
_CACHE_TTL = 3600 * 24  # 24 hours

USER_AGENT = "TablatureApp/1.0 (https://github.com/tablatures)"


def _get_cached(key: str) -> Optional[dict]:
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    return None


def _set_cached(key: str, data: dict):
    _cache[key] = {"data": data, "ts": time.time()}


def search_musicbrainz_artist(artist_name: str) -> Optional[dict]:
    """Search MusicBrainz for an artist and return MBID + basic info."""
    cache_key = f"mb_artist:{artist_name.lower()}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        resp = requests.get(
            "https://musicbrainz.org/ws/2/artist/",
            params={"query": artist_name, "fmt": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            artists = data.get("artists", [])
            if artists:
                artist = artists[0]
                result = {
                    "mbid": artist.get("id"),
                    "name": artist.get("name"),
                    "country": artist.get("country"),
                    "type": artist.get("type"),
                    "disambiguation": artist.get("disambiguation", ""),
                    "tags": [t["name"] for t in artist.get("tags", [])[:5]],
                }
                _set_cached(cache_key, result)
                return result
    except Exception as e:
        logger.warning("MusicBrainz artist search failed: %s", e)
    return None


def get_artist_image(artist_name: str) -> Optional[str]:
    """Try to get artist image URL from TheAudioDB (free, no auth for basic)."""
    cache_key = f"audiodb_img:{artist_name.lower()}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached.get("url")

    try:
        resp = requests.get(
            "https://www.theaudiodb.com/api/v1/json/2/search.php",
            params={"s": artist_name},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            artists = data.get("artists") or []
            if artists:
                a = artists[0]
                url = (
                    a.get("strArtistThumb")
                    or a.get("strArtistFanart")
                    or a.get("strArtistLogo")
                    or ""
                )
                bio = a.get("strBiographyEN", "")
                result = {"url": url, "bio": bio[:500] if bio else ""}
                _set_cached(cache_key, result)
                return url
    except Exception as e:
        logger.warning("TheAudioDB image fetch failed: %s", e)
    return None


def get_artist_info(artist_name: str) -> dict:
    """Get combined artist info from multiple sources."""
    cache_key = f"artist_info:{artist_name.lower()}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    result = {
        "name": artist_name,
        "image": None,
        "bio": None,
        "country": None,
        "tags": [],
        "mbid": None,
    }

    # MusicBrainz for metadata
    mb = search_musicbrainz_artist(artist_name)
    if mb:
        result["mbid"] = mb.get("mbid")
        result["country"] = mb.get("country")
        result["tags"] = mb.get("tags", [])
        result["name"] = mb.get("name", artist_name)

    # TheAudioDB for image + bio
    try:
        resp = requests.get(
            "https://www.theaudiodb.com/api/v1/json/2/search.php",
            params={"s": artist_name},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            artists = data.get("artists") or []
            if artists:
                a = artists[0]
                result["image"] = (
                    a.get("strArtistThumb")
                    or a.get("strArtistFanart")
                    or a.get("strArtistLogo")
                )
                bio = a.get("strBiographyEN", "")
                result["bio"] = bio[:500] if bio else None
    except Exception as e:
        logger.warning("TheAudioDB fetch failed: %s", e)

    # iTunes fallback for image
    if not result["image"]:
        try:
            resp = requests.get(
                "https://itunes.apple.com/search",
                params={"term": artist_name, "entity": "musicArtist", "limit": 1},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                results_list = data.get("results", [])
                if results_list:
                    # iTunes doesn't always have artist images but has artwork
                    pass
        except:
            pass

    _set_cached(cache_key, result)
    return result


def get_song_artwork(artist: str, title: str) -> Optional[str]:
    """Get album artwork for a song via iTunes Search API."""
    cache_key = f"artwork:{artist.lower()}:{title.lower()}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached.get("url")

    try:
        resp = requests.get(
            "https://itunes.apple.com/search",
            params={"term": f"{artist} {title}", "entity": "song", "limit": 1},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            results_list = data.get("results", [])
            if results_list:
                # Get high-res artwork (replace 100x100 with 600x600)
                artwork = results_list[0].get("artworkUrl100", "")
                if artwork:
                    artwork = artwork.replace("100x100", "600x600")
                    _set_cached(cache_key, {"url": artwork})
                    return artwork
    except Exception as e:
        logger.warning("iTunes artwork fetch failed: %s", e)
    return None


def search_youtube(query: str, limit: int = 5) -> list:
    """Search YouTube for videos matching query. Uses scraping approach (no API key needed)."""
    cache_key = f"yt:{query.lower()}:{limit}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        # Use YouTube's internal search endpoint
        import urllib.parse
        encoded = urllib.parse.quote(query)
        resp = requests.get(
            f"https://www.youtube.com/results?search_query={encoded}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return []

        # Extract video data from the page's initial data
        import re
        import json

        match = re.search(r'var ytInitialData = ({.*?});</script>', resp.text)
        if not match:
            return []

        yt_data = json.loads(match.group(1))

        results = []
        try:
            contents = (
                yt_data.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [{}])[0]
                .get("itemSectionRenderer", {})
                .get("contents", [])
            )

            for item in contents:
                video = item.get("videoRenderer")
                if not video:
                    continue
                video_id = video.get("videoId")
                if not video_id:
                    continue

                title_runs = video.get("title", {}).get("runs", [])
                title_text = title_runs[0].get("text", "") if title_runs else ""

                channel_runs = video.get("ownerText", {}).get("runs", [])
                channel = channel_runs[0].get("text", "") if channel_runs else ""

                length_text = video.get("lengthText", {}).get("simpleText", "")

                thumbnail = ""
                thumbs = video.get("thumbnail", {}).get("thumbnails", [])
                if thumbs:
                    thumbnail = thumbs[-1].get("url", "")

                results.append({
                    "videoId": video_id,
                    "title": title_text,
                    "channel": channel,
                    "duration": length_text,
                    "thumbnail": thumbnail,
                })

                if len(results) >= limit:
                    break
        except (KeyError, IndexError):
            pass

        _set_cached(cache_key, results)
        return results

    except Exception as e:
        logger.warning("YouTube search failed: %s", e)
        return []
