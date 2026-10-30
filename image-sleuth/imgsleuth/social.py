"""Recognise social media links in results so they can be labelled and listed first.

Social sites don't offer reverse image search themselves; their public posts
reach us through the general engines (Yandex, TinEye, Google, Bing), which
index them.
"""
from __future__ import annotations

from urllib.parse import urlsplit

PLATFORMS = {
    "instagram.com": "Instagram", "cdninstagram.com": "Instagram",
    "facebook.com": "Facebook", "fb.com": "Facebook", "fbcdn.net": "Facebook",
    "tiktok.com": "TikTok", "twitter.com": "X", "x.com": "X", "twimg.com": "X",
    "reddit.com": "Reddit", "redd.it": "Reddit", "redditmedia.com": "Reddit",
    "pinterest.com": "Pinterest", "pinimg.com": "Pinterest",
    "youtube.com": "YouTube", "ytimg.com": "YouTube", "linkedin.com": "LinkedIn",
    "tumblr.com": "Tumblr", "vk.com": "VK", "vkontakte.ru": "VK", "ok.ru": "OK",
    "threads.net": "Threads", "bsky.app": "Bluesky", "snapchat.com": "Snapchat",
    "flickr.com": "Flickr", "deviantart.com": "DeviantArt", "imgur.com": "Imgur",
    "telegram.me": "Telegram", "t.me": "Telegram", "weibo.com": "Weibo",
    "quora.com": "Quora", "9gag.com": "9GAG", "twitch.tv": "Twitch",
    "discord.com": "Discord", "mastodon.social": "Mastodon",
}


# Sites that also run country domains (pinterest.de, facebook.co.uk, ...).
_BRANDS = {d.split(".")[0]: n for d, n in PLATFORMS.items() if d.endswith(".com") and len(d.split(".")) == 2}


def platform(url: str) -> str:
    """Return the social platform name for a URL, or '' if it isn't one."""
    host = urlsplit(url).netloc.lower().split(":")[0]
    parts = host.split(".")
    for i in range(len(parts) - 1):
        name = PLATFORMS.get(".".join(parts[i:]))
        if name:
            return name
        tail = parts[i + 1:]
        if parts[i] in _BRANDS and 1 <= len(tail) <= 2 and all(len(t) <= 3 for t in tail):
            return _BRANDS[parts[i]]
    return ""
