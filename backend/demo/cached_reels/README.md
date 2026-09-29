# Cached reel extractions

`combine.py` checks this folder before downloading a public Reel. A successful
URL run writes one JSON file with the normalized source URL and the full
extraction contract output. This keeps demos repeatable when Instagram blocks
or rate-limits a later request.

The target Reel `https://www.instagram.com/reels/DbfsdUnvDqM/` should be
cached here by one successful real run. Do not fabricate its extraction. If
Instagram returns 429 or another download failure, keep this folder empty and
use caption/upload fallback until a real run succeeds.
