"""
Downloads media from a public URL (an Instagram Reel or a photo post)
so the rest of the pipeline can process it the same way as a directly
uploaded file.

Uses yt-dlp, a well-maintained, widely used open-source downloader that
supports Instagram's public post/reel URLs without requiring login
credentials, for video content. This is a meaningfully different,
lower-risk approach than the private-API scraping tools flagged earlier
in planning (see docs/spec.md Section 8: "Explicitly not supported:
reading a user's Instagram Saved folder automatically, or requesting
Instagram login credentials") — this only fetches a public post a user
has explicitly pasted a link to, the same way a link preview would. It
does not access anyone's account, saved folder, or private content, and
never asks for or stores a password.

For photo-only posts, yt-dlp's Instagram extractor raises an error
outright — it's built primarily for video. Photo posts use instaloader
instead, a library purpose-built for fetching Instagram posts, which
returns the actual full-resolution original image via the post's
shortcode. An earlier version of this file used the page's og:image
link-preview tag instead, but real testing showed that tag points to a
cropped, low-resolution thumbnail that cut off real content.

IMPORTANT — this is a best-effort feature, not a guaranteed one. Neither
yt-dlp nor instaloader is an official Instagram API, and Meta's actual
official oEmbed API (checked directly) both no longer returns a
downloadable image URL and explicitly prohibits extracting/persisting
content for anything beyond rendering an embed — so there's no fully
official, compliant path to this at all. Anonymous access can and does
get rate-limited or blocked. When auto-fetch fails, callers should catch
AutoFetchFailed and fall back to asking the user to upload the file
manually — that path always works regardless of what Instagram does.
"""

import os
import re
import uuid

import instaloader
import requests
import yt_dlp


class AutoFetchFailed(Exception):
    """
    Raised whenever auto-fetching from a URL doesn't work, for any
    reason — private post, deleted post, rate limiting, a multi-image
    carousel, Instagram changing something, etc. Callers should catch
    this specifically and fall back to manual upload, rather than
    showing a raw error or stack trace to the user. The message is
    written to be shown to an end user directly.
    """
    pass


def is_url(value):
    """Quick check for whether a given input string is a URL, not a local file path."""
    return value.startswith("http://") or value.startswith("https://")


def download_media_from_url(url, output_dir="./_downloaded_media"):
    """
    Downloads either a video or a photo from a public Instagram post URL.

    Returns (local_path, media_type), where media_type is "video" or
    "image" — the caller (pipeline.py) uses this to decide whether to
    run frame extraction or treat the file as a single static image.

    Tries yt-dlp first (works for Reels and other video posts). If
    yt-dlp reports "no video in this post" specifically, falls back to
    instaloader for the photo-post path. Any failure at any point raises
    AutoFetchFailed with a message meant to be shown directly to the
    user — the caller should catch this and offer manual upload instead.
    """
    os.makedirs(output_dir, exist_ok=True)
    unique_id = uuid.uuid4().hex

    try:
        return _download_video(url, output_dir, unique_id), "video"
    except _NoVideoInPost:
        pass  # fall through to the photo-post path below
    except Exception as e:
        raise AutoFetchFailed(
            "Couldn't automatically fetch this post — it may be private, deleted, "
            "or the link may be invalid. Please save it and upload it directly instead."
        ) from e

    try:
        return _download_via_instaloader(url, output_dir, unique_id), "image"
    except Exception as e:
        raise AutoFetchFailed(
            "Couldn't automatically fetch this photo post — this can happen due to "
            "Instagram rate limits, a private post, or a multi-image carousel (not "
            "yet supported). Please save it and upload it directly instead."
        ) from e


class _NoVideoInPost(Exception):
    """Internal signal that yt-dlp found a post with no video, so the caller should try the photo-post fallback."""
    pass


def _download_video(url, output_dir, unique_id):
    output_template = os.path.join(output_dir, f"{unique_id}.%(ext)s")
    video_opts = {
        "outtmpl": output_template,
        "format": "mp4/best",
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(video_opts) as ydl:
            result_info = ydl.extract_info(url, download=True)
            downloaded_path = ydl.prepare_filename(result_info)
    except yt_dlp.utils.DownloadError as e:
        if "no video" in str(e).lower():
            raise _NoVideoInPost() from e
        raise

    if not os.path.exists(downloaded_path):
        raise ValueError(f"Video download reported success but file not found: {downloaded_path}")

    return downloaded_path


def _extract_shortcode(url):
    """
    Extracts the post/reel shortcode from an Instagram URL, e.g.
    "https://www.instagram.com/p/Dcx0j45MRrp/?stkn=..." -> "Dcx0j45MRrp"
    """
    match = re.search(r'/(?:p|reel)/([^/?]+)', url)
    if not match:
        raise ValueError(f"Could not find a post/reel ID in URL: {url}")
    return match.group(1)


def _download_via_instaloader(url, output_dir, unique_id):
    """
    Fallback for photo-only posts. Fetches the actual full-resolution
    post image via instaloader, using the shortcode extracted from the URL.
    Any failure here is caught by the caller and turned into AutoFetchFailed.
    """
    shortcode = _extract_shortcode(url)
    loader = instaloader.Instaloader(
        download_videos=False,
        download_comments=False,
        save_metadata=False,
        quiet=True,
    )

    post = instaloader.Post.from_shortcode(loader.context, shortcode)

    if post.is_video:
        # Shouldn't normally reach here since yt-dlp handles video posts,
        # but keep this as an honest signal rather than silently treating
        # a video URL as an image.
        raise ValueError(f"Post {shortcode} is a video — this should have been caught by the video path.")

    if getattr(post, "typename", None) == "GraphSidecar":
        raise ValueError(f"Post {shortcode} is a multi-image carousel, which isn't supported yet.")

    image_url = post.url  # full-resolution display image, not a cropped preview
    image_path = os.path.join(output_dir, f"{unique_id}.jpg")

    response = requests.get(image_url, timeout=15)
    response.raise_for_status()
    with open(image_path, "wb") as f:
        f.write(response.content)

    return image_path