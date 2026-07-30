"""Fetch GGUF metadata for a Hugging Face repo without downloading the model weights.

Uses HF's `?expand[]=gguf` API, which parses the GGUF header server-side and
returns chat_template, bos/eos tokens, context_length, and file size info in a
single small HTTP response.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

import requests

HF_API_BASE = "https://huggingface.co/api/models"

# HF's public API rate-limits unauthenticated clients under sustained request
# volume (observed: HTTP 429 on ~2/3 of requests after a few hundred prior
# calls in the same session). Retry with exponential backoff rather than
# silently recording a failure -- a 429 is not evidence of "no data", and
# treating it as one would corrupt the prevalence measurement this audit
# exists to produce.
MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 2.0


def _get_with_retry(url: str, timeout: int) -> requests.Response:
    last_exc = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=timeout)
        except requests.RequestException as e:
            last_exc = e
            time.sleep(BASE_BACKOFF_SECONDS * (2**attempt))
            continue
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else BASE_BACKOFF_SECONDS * (2**attempt)
            time.sleep(wait)
            continue
        return resp
    if last_exc:
        raise last_exc
    return resp  # last 429 response, exhausted retries


@dataclass
class HFGGUFRecord:
    repo: str
    ok: bool
    error: str | None = None
    n_gguf_files: int = 0
    gguf_filenames: list[str] = field(default_factory=list)
    architecture: str | None = None
    context_length: int | None = None
    bos_token: str | None = None
    eos_token: str | None = None
    chat_template: str | None = None
    chat_template_len: int = 0
    chat_template_sha256: str | None = None
    total_file_size: int | None = None


def fetch_repo_file_listing(repo: str, timeout: int = 20) -> tuple[bool, list[str], str | None]:
    """Return (ok, gguf_filenames, error)."""
    try:
        resp = _get_with_retry(f"{HF_API_BASE}/{repo}", timeout=timeout)
    except requests.RequestException as e:
        return False, [], f"request_error: {e}"
    if resp.status_code != 200:
        return False, [], f"http_{resp.status_code}"
    data = resp.json()
    siblings = data.get("siblings", [])
    gguf_files = [s["rfilename"] for s in siblings if s["rfilename"].lower().endswith(".gguf")]
    return True, gguf_files, None


def fetch_gguf_metadata(repo: str, timeout: int = 20) -> HFGGUFRecord:
    """Fetch parsed GGUF metadata for a repo via the expand[]=gguf API.

    Note: HF's expand API returns metadata for a single representative file in
    the repo (typically the first/primary one), not per-file. Callers who need
    per-quant-file granularity should cross-check `n_gguf_files` and consider
    this a repo-level (not file-level) signal unless verified otherwise.
    """
    listing_ok, gguf_files, listing_err = fetch_repo_file_listing(repo, timeout=timeout)
    if not listing_ok:
        return HFGGUFRecord(repo=repo, ok=False, error=listing_err)
    if not gguf_files:
        return HFGGUFRecord(repo=repo, ok=False, error="no_gguf_files_in_repo", n_gguf_files=0)

    try:
        resp = _get_with_retry(f"{HF_API_BASE}/{repo}?expand[]=gguf", timeout=timeout)
    except requests.RequestException as e:
        return HFGGUFRecord(
            repo=repo, ok=False, error=f"request_error: {e}",
            n_gguf_files=len(gguf_files), gguf_filenames=gguf_files,
        )
    if resp.status_code != 200:
        return HFGGUFRecord(
            repo=repo, ok=False, error=f"http_{resp.status_code}",
            n_gguf_files=len(gguf_files), gguf_filenames=gguf_files,
        )

    data = resp.json()
    gguf = data.get("gguf")
    if not gguf:
        return HFGGUFRecord(
            repo=repo, ok=False, error="expand_api_returned_no_gguf_field",
            n_gguf_files=len(gguf_files), gguf_filenames=gguf_files,
        )

    chat_template = gguf.get("chat_template")
    ct_len = len(chat_template) if chat_template else 0
    ct_hash = hashlib.sha256(chat_template.encode()).hexdigest() if chat_template else None

    return HFGGUFRecord(
        repo=repo,
        ok=True,
        n_gguf_files=len(gguf_files),
        gguf_filenames=gguf_files,
        architecture=gguf.get("architecture"),
        context_length=gguf.get("context_length"),
        bos_token=gguf.get("bos_token"),
        eos_token=gguf.get("eos_token"),
        chat_template=chat_template,
        chat_template_len=ct_len,
        chat_template_sha256=ct_hash,
        total_file_size=gguf.get("totalFileSize"),
    )
