import os
import json
import re
import urllib.request

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timezone
from urllib.parse import urlparse
from pathlib import Path


try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


# ============================================================
# SETTINGS
# ============================================================

# API key is entered through Settings and kept in memory only.
YOUTUBE_API_KEY = ""

# Minimum score required for a result to appear.
MIN_SCORE = 25

# Maximum account age included in analysis.
MAX_ANALYSIS_ACCOUNT_AGE_DAYS = 10

# Maximum possible score.
MAX_SCORE = 50

REPORT_GROUP_NAME = (
    "CLANk, Clanker Logging & Analysis Network"
)

PROFILE_IMAGE_FOLDER = (
    Path("reports") / "profile_images"
)

youtube = None


# ============================================================
# YOUTUBE API
# ============================================================

def youtube_api_available(api_key=None):
    return bool((api_key if api_key is not None else YOUTUBE_API_KEY).strip())


def get_youtube_service(api_key=None):
    key = api_key if api_key is not None else YOUTUBE_API_KEY
    if not key or not key.strip():
        raise RuntimeError("No YouTube API key configured.")
    return build("youtube", "v3", developerKey=key.strip())


def youtube_error_message(error):
    """
    Converts common YouTube API errors into useful messages.
    """

    if isinstance(error, HttpError):
        status = getattr(
            error.resp,
            "status",
            None
        )

        error_text = str(error)

        if status == 403 and (
            "quotaExceeded" in error_text
            or "quota" in error_text.lower()
        ):
            return (
                "YouTube API quota exceeded.\n\n"
                "Google has temporarily stopped allowing "
                "requests from this API key because its "
                "daily quota has been used.\n\n"
                "The application is already configured to "
                "scan all available comment pages. There "
                "is no artificial comment limit in this "
                "version.\n\n"
                "You will need to wait for the API quota "
                "to reset or use another API project/key."
            )

        if status == 403:
            return (
                "YouTube rejected the API request (403).\n\n"
                "This can happen if the API is disabled, "
                "the API key restrictions are incorrect, "
                "or the requested resource is unavailable."
            )

        if status == 400:
            return (
                "YouTube rejected the request (400).\n\n"
                "The video may be unavailable or the URL "
                "may not refer to a valid video."
            )

        if status == 404:
            return (
                "YouTube could not find the requested video "
                "or resource."
            )

    return str(error)


# ============================================================
# URL / TEXT HELPERS
# ============================================================

def video_id_from_url(url):
    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"youtu\.be/([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})"
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            url
        )

        if match:
            return match.group(1)

    return None


def account_age_days(created):
    if not created or created == "Unknown":
        return None

    try:
        date = datetime.fromisoformat(
            created.replace(
                "Z",
                "+00:00"
            )
        )

        now = datetime.now(
            timezone.utc
        )

        return (
            now - date
        ).days

    except Exception:
        return None


def find_domains(text):
    urls = re.findall(
        r"(?:https?://|www\.)[^\s]+",
        text,
        flags=re.IGNORECASE
    )

    domains = []

    for url in urls:
        url = url.rstrip(
            ".,!?;:)]}"
        )

        if not url.startswith("http"):
            url = "https://" + url

        try:
            domain = urlparse(
                url
            ).netloc.lower()

            if domain.startswith("www."):
                domain = domain[4:]

            if domain:
                domains.append(domain)

        except Exception:
            pass

    return domains


def find_youtube_references(text):
    references = set()

    channel_ids = re.findall(
        r"youtube\.com/channel/(UC[A-Za-z0-9_-]{20,})",
        text,
        flags=re.IGNORECASE
    )

    for channel_id in channel_ids:
        references.add(
            channel_id
        )

    handles = re.findall(
        r"(?:youtube\.com/)?@([A-Za-z0-9._-]{3,30})",
        text,
        flags=re.IGNORECASE
    )

    for handle in handles:
        references.add(
            "HANDLE:" + handle.lower()
        )

    custom_urls = re.findall(
        r"youtube\.com/(?:c|user)/([A-Za-z0-9._-]{3,100})",
        text,
        flags=re.IGNORECASE
    )

    for name in custom_urls:
        references.add(
            "NAME:" + name.lower()
        )

    return references


# ============================================================
# COMMENTS
# ============================================================

def get_comments(video_id, progress_callback=None, api_key=None):
    """
    Downloads ALL available top-level comments.

    There is intentionally NO artificial comment limit.

    YouTube returns comments in pages of up to 100. This
    function continues requesting pages until YouTube no
    longer supplies a nextPageToken.

    Note:
    YouTube API quota still applies. The program cannot
    bypass Google's quota system.
    """

    api = get_youtube_service(api_key)

    all_comments = []
    next_page = None
    page_number = 0

    while True:
        page_number += 1

        if progress_callback:
            progress_callback(
                f"Downloading comments... "
                f"{len(all_comments):,} collected"
            )

        request_kwargs = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": 100,
            "textFormat": "plainText"
        }

        if next_page:
            request_kwargs[
                "pageToken"
            ] = next_page

        try:
            result = (
                api.commentThreads()
                .list(**request_kwargs)
                .execute()
            )

        except HttpError:
            raise

        for item in result.get(
            "items",
            []
        ):
            try:
                snippet = (
                    item["snippet"]
                    ["topLevelComment"]
                    ["snippet"]
                )

            except KeyError:
                continue

            channel_id = (
                snippet
                .get(
                    "authorChannelId",
                    {}
                )
                .get(
                    "value"
                )
            )

            if not channel_id:
                continue

            all_comments.append({
                "channel_id": channel_id,
                "name": snippet.get(
                    "authorDisplayName",
                    "Unknown"
                ),
                "text": snippet.get(
                    "textDisplay",
                    ""
                ),
                "profile_image": snippet.get(
                    "authorProfileImageUrl",
                    ""
                )
            })

        next_page = result.get(
            "nextPageToken"
        )

        if not next_page:
            break

    if progress_callback:
        progress_callback(
            f"Finished downloading "
            f"{len(all_comments):,} comments"
        )

    return all_comments


def get_unique_channels(comments):
    channels = {}

    for comment in comments:
        channel_id = comment[
            "channel_id"
        ]

        if channel_id not in channels:
            channels[channel_id] = {
                "name": comment["name"],
                "channel_id": channel_id,
                "channel_url": (
                    "https://www.youtube.com/channel/"
                    + channel_id
                ),
                "profile_image": comment[
                    "profile_image"
                ],
                "comments": []
            }

        channels[channel_id][
            "comments"
        ].append(
            comment["text"]
        )

    return channels


# ============================================================
# CHANNEL INFORMATION
# ============================================================

def get_channel_information(
    channel_ids,
    progress_callback=None,
    api_key=None
):
    api = get_youtube_service(api_key)

    channels = {}

    for start in range(
        0,
        len(channel_ids),
        50
    ):
        batch = channel_ids[
            start:start + 50
        ]

        if progress_callback:
            progress_callback(
                f"Loading account information... "
                f"{min(start + 50, len(channel_ids)):,}/"
                f"{len(channel_ids):,}"
            )

        result = api.channels().list(
            part="snippet,statistics",
            id=",".join(batch)
        ).execute()

        for channel in result.get(
            "items",
            []
        ):
            snippet = channel.get(
                "snippet",
                {}
            )

            statistics = channel.get(
                "statistics",
                {}
            )

            channel_id = channel["id"]

            channels[channel_id] = {
                "name": snippet.get(
                    "title",
                    "Unknown"
                ),
                "description": snippet.get(
                    "description",
                    ""
                ),
                "created": snippet.get(
                    "publishedAt",
                    "Unknown"
                ),
                "videos": statistics.get(
                    "videoCount",
                    "Unknown"
                ),
                "subscribers": statistics.get(
                    "subscriberCount",
                    "Unknown"
                ),
                "channel_url": (
                    "https://www.youtube.com/channel/"
                    + channel_id
                )
            }

    return channels


# ============================================================
# NETWORK ANALYSIS
# ============================================================

def build_domain_connections(channels):
    domain_accounts = {}

    for channel_id, channel in channels.items():
        domains = set()

        for comment in channel[
            "comments"
        ]:
            domains.update(
                find_domains(comment)
            )

        for domain in domains:
            if domain not in domain_accounts:
                domain_accounts[domain] = set()

            domain_accounts[
                domain
            ].add(
                channel_id
            )

    return domain_accounts


def build_youtube_connections(
    channels,
    channel_infos
):
    connections = {}

    for channel_id, channel in channels.items():
        info = channel_infos.get(
            channel_id
        )

        if not info:
            continue

        references = set()

        references.update(
            find_youtube_references(
                info["description"]
            )
        )

        for comment in channel[
            "comments"
        ]:
            references.update(
                find_youtube_references(
                    comment
                )
            )

        connections[
            channel_id
        ] = references

    return connections


# ============================================================
# SCORING
# ============================================================

def calculate_score(
    channel_id,
    channel,
    channel_info,
    domain_accounts,
    youtube_connections,
    all_channel_ids
):
    """
    Maximum score = 50.

    The scoring uses the original 50-point scale.
    """

    score = 0
    reasons = []
    flags = []

    # --------------------------------------------------------
    # ACCOUNT AGE
    # --------------------------------------------------------

    age = account_age_days(
        channel_info["created"]
    )

    if age is not None:

        if age <= 3:
            score += 50

            reason = (
                f"Account is only {age} days old"
            )

            reasons.append(reason)
            flags.append("Very new account")

        elif age <= 7:
            score += 15

            reason = (
                f"Account is only {age} days old"
            )

            reasons.append(reason)
            flags.append("New account")

        elif age <= 30:
            score += 10

            reason = (
                f"Account is only {age} days old"
            )

            reasons.append(reason)
            flags.append("Recently created account")

    # --------------------------------------------------------
    # VIDEOS
    # --------------------------------------------------------

    try:
        videos = int(
            channel_info["videos"]
        )

        if videos == 0:
            score += 10

            reasons.append(
                "No public videos"
            )

            flags.append(
                "No public videos"
            )

        elif videos <= 2:
            score += 10

            reasons.append(
                f"Only {videos} public videos"
            )

            flags.append(
                "Very few public videos"
            )

    except Exception:
        pass

    # --------------------------------------------------------
    # CHANNEL DESCRIPTION LINKS
    # --------------------------------------------------------

    description_domains = find_domains(
        channel_info["description"]
    )

    if description_domains:
        score += 10

        reasons.append(
            "Links found in channel description"
        )

        flags.append(
            "Links in description"
        )

    # --------------------------------------------------------
    # COMMENT COUNT
    # --------------------------------------------------------

    comment_count = len(
        channel["comments"]
    )

    if comment_count >= 3:
        score += 5

        reasons.append(
            f"{comment_count} comments under this video"
        )

        flags.append(
            "Multiple comments"
        )

    # --------------------------------------------------------
    # LINKS IN COMMENTS
    # --------------------------------------------------------

    own_domains = set()

    for comment in channel[
        "comments"
    ]:
        own_domains.update(
            find_domains(comment)
        )

    if own_domains:
        score += 10

        reasons.append(
            "Links found in comments"
        )

        flags.append(
            "Links in comments"
        )

    # --------------------------------------------------------
    # SHARED DOMAINS
    # --------------------------------------------------------

    shared_domain_found = False

    for domain in own_domains:
        others = (
            domain_accounts.get(
                domain,
                set()
            )
            - {channel_id}
        )

        if others:
            score += 10

            reasons.append(
                f"Domain '{domain}' also used "
                "by other accounts"
            )

            flags.append(
                "Shared website/domain"
            )

            shared_domain_found = True
            break

    # --------------------------------------------------------
    # YOUTUBE REFERENCES
    # --------------------------------------------------------

    own_references = (
        youtube_connections.get(
            channel_id,
            set()
        )
    )

    if own_references:
        score += 10

        reasons.append(
            f"{len(own_references)} YouTube "
            "references found"
        )

        flags.append(
            "YouTube references"
        )

    # --------------------------------------------------------
    # DIRECT ACCOUNT CONNECTIONS
    # --------------------------------------------------------

    connected_accounts = []

    for reference in own_references:

        if (
            reference.startswith("UC")
            and reference in all_channel_ids
            and reference != channel_id
        ):
            connected_accounts.append(
                reference
            )

    if connected_accounts:
        score += 15

        reasons.append(
            f"{len(connected_accounts)} directly "
            "connected matching accounts"
        )

        flags.append(
            "Connected accounts"
        )

    # --------------------------------------------------------
    # CAP SCORE
    # --------------------------------------------------------

    score = min(
        score,
        MAX_SCORE
    )

    # --------------------------------------------------------
    # CLASSIFICATION
    # --------------------------------------------------------

    if score >= 80:
        classification = (
            "HIGHLY SUSPICIOUS"
        )

    elif score >= 60:
        classification = (
            "SUSPICIOUS"
        )

    else:
        classification = (
            "REVIEW"
        )

    # Remove duplicate flags.
    flags = list(
        dict.fromkeys(flags)
    )

    return (
        score,
        classification,
        reasons,
        connected_accounts,
        flags
    )


# ============================================================
# PROFILE IMAGE
# ============================================================

def save_profile_image(
    url,
    channel_id
):
    if not url:
        return None

    try:
        PROFILE_IMAGE_FOLDER.mkdir(
            parents=True,
            exist_ok=True
        )

        file = (
            PROFILE_IMAGE_FOLDER
            / f"{channel_id}.jpg"
        )

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent":
                    "Mozilla/5.0"
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=15
        ) as response:
            data = response.read()

        with open(
            file,
            "wb"
        ) as f:
            f.write(data)

        return str(file)

    except Exception as error:
        print(
            "Profile image could not be saved:",
            error
        )

        return None


# ============================================================
# REPORT GENERATION
# ============================================================

def create_report_text(
    result,
    profile_image=False
):
    reasons = []

    reasons.append(
        "Spam bot promoting and spreading adult-rated websites"
    )

    has_links = False

    if find_domains(
        result.get(
            "comment",
            ""
        )
    ):
        has_links = True

    for reason in result.get(
        "reasons",
        []
    ):
        if (
            "link" in reason.lower()
            or "domain" in reason.lower()
            or "website" in reason.lower()
        ):
            has_links = True
            break

    if has_links:
        reasons.append(
            "Suspicious links"
        )

    if profile_image:
        reasons.append(
            "Sexual profile picture"
        )

    unique_reasons = []

    for reason in reasons:
        if reason not in unique_reasons:
            unique_reasons.append(
                reason
            )

    reason_text = "\n".join(
        "- " + reason
        for reason in unique_reasons
    )

    return f"""
REPORT – PREPARED BY: {REPORT_GROUP_NAME}

Reason for report:

Spam bot promoting and spreading adult-rated websites.

Observed reasons:
{reason_text}
""".strip()


