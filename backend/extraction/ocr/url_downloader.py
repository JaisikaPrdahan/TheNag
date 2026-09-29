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

Also extracts caption text, hashtags, and the post's original publish
date from the post where available (yt-dlp's info dict for video
posts, instaloader's Post object for photo posts) — caption/hashtags
feed Person 2's classification per docs/spec.md Section 1/2, and the
post date is what relative-date resolution ("next Friday", "in 2
weeks") must be calculated against, not whenever classification
happens to run — a reel processed days after posting would otherwise
resolve "next Friday" to the wrong date entirely.
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


def extract_hashtags(caption_text):
    """
    Pulls hashtags out of caption text as their own list, per
    docs/spec.md Section 1/2 — hashtags are a distinct, high-value
    classification signal and shouldn't be buried inside the raw
    caption string. Returns hashtag words without the '#' symbol.
    """
    if not caption_text:
        return []
    return re.findall(r"#(\w+)", caption_text)


def download_media_from_url(url, output_dir="./_downloaded_media"):
    """
    Downloads either a video or a photo from a public Instagram post URL.

    Returns a dict:
        {
            "path": str,                # local file path
            "media_type": "video" | "image",
            "caption_text": str or None,
            "hashtags": [str, ...],
            "post_date": str or None,   # ISO 8601, the post's own publish date
        }

    Tries yt-dlp first (works for Reels and other video posts). If
    yt-dlp reports "no video in this post" specifically, falls back to
    instaloader for the photo-post path. Any failure at any point raises
    AutoFetchFailed with a message meant to be shown directly to the
    user — the caller should catch this and offer manual upload instead.
    """
    os.makedirs(output_dir, exist_ok=True)
    unique_id = uuid.uuid4().hex

    try:
        path, caption_text, post_date = _download_video(url, output_dir, unique_id)
        return {
            "path": path,
            "media_type": "video",
            "caption_text": caption_text,
            "hashtags": extract_hashtags(caption_text),
            "post_date": post_date,
        }
    except _NoVideoInPost:
        pass  # fall through to the photo-post path below
    except Exception as e:
        if "429" in str(e) or "rate limit" in str(e).lower():
            raise AutoFetchFailed(
                "Instagram rate-limited this request. TheNag will not retry automatically; "
                "please use a cached reel later or upload the file directly instead."
            ) from e
        raise AutoFetchFailed(
            "Couldn't automatically fetch this post — it may be private, deleted, "
            "or the link may be invalid. Please save it and upload it directly instead."
        ) from e

    try:
        path, caption_text, post_date = _download_via_instaloader(url, output_dir, unique_id)
        return {
            "path": path,
            "media_type": "image",
            "caption_text": caption_text,
            "hashtags": extract_hashtags(caption_text),
            "post_date": post_date,
        }
    except Exception as e:
        if "429" in str(e) or "rate limit" in str(e).lower():
            raise AutoFetchFailed(
                "Instagram rate-limited this request. TheNag will not retry automatically; "
                "please use a cached reel later or upload the file directly instead."
            ) from e
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
        # Explicitly request best video + best audio, merged into one
        # mp4 file. Some platforms (confirmed with a YouTube Shorts
        # test) serve video and audio as separate streams — a plain
        # "mp4/best" selector can silently grab a video-only stream if
        # no single combined format exists, producing a file with no
        # audio track at all and no error until Whisper tries to read
        # it. "bestvideo+bestaudio" forces yt-dlp to merge them via
        # FFmpeg, which is already required elsewhere in this pipeline.
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(video_opts) as ydl:
            result_info = ydl.extract_info(url, download=True)
            downloaded_path = ydl.prepare_filename(result_info)
            # merge_output_format can change the actual extension from
            # what prepare_filename predicts before merging happens —
            # correct it if the merged file ended up as .mp4 but the
            # predicted path wasn't.
            if not os.path.exists(downloaded_path):
                mp4_path = os.path.splitext(downloaded_path)[0] + ".mp4"
                if os.path.exists(mp4_path):
                    downloaded_path = mp4_path
    except yt_dlp.utils.DownloadError as e:
        if "no video" in str(e).lower():
            raise _NoVideoInPost() from e
        raise

    if not os.path.exists(downloaded_path):
        raise ValueError(f"Video download reported success but file not found: {downloaded_path}")

    # yt-dlp puts the post caption in "description" for most platforms,
    # including Instagram. Not guaranteed to always be present.
    caption_text = result_info.get("description")

    # yt-dlp's "upload_date" is a "YYYYMMDD" string (date only, no
    # time), or absent entirely. Normalize to ISO 8601 so both download
    # paths return the same format for callers to parse.
    post_date = None
    raw_upload_date = result_info.get("upload_date")
    if raw_upload_date and len(raw_upload_date) == 8:
        post_date = f"{raw_upload_date[0:4]}-{raw_upload_date[4:6]}-{raw_upload_date[6:8]}"

    return downloaded_path, caption_text, post_date


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

    # instaloader's Post.caption is the actual post caption text.
    caption_text = post.caption

    # Post.date_utc is a real datetime object (UTC) — already has
    # both date and time, unlike yt-dlp's date-only string.
    post_date = post.date_utc.isoformat() if post.date_utc else None

    return image_path, caption_text, post_date
