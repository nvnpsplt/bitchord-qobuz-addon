import hashlib
from typing import Union


def generate_file_url_signature(
    track_id: Union[int, str],
    format_id: Union[int, str],
    request_ts: Union[int, str],
    app_secret: str,
    intent: str = "stream",
) -> str:
    """
    Generate request_sig for Qobuz API endpoint 'track/getFileUrl'.

    The signature is computed by concatenating:
    - endpoint name ('trackgetFileUrl')
    - parameters in alphabetical order:
        - 'format_id' + format_id
        - 'intent' + intent
        - 'track_id' + track_id
    - timestamp (request_ts)
    - app_secret

    Then hashing the UTF-8 encoded string with MD5.

    Formula:
    MD5("trackgetFileUrl" + "format_id" + fmt + "intent" + intent + "track_id" + tid + ts + secret)
    """
    sig_raw = (
        f"trackgetFileUrl"
        f"format_id{format_id}"
        f"intent{intent}"
        f"track_id{track_id}"
        f"{request_ts}"
        f"{app_secret}"
    )
    return hashlib.md5(sig_raw.encode("utf-8")).hexdigest()


def generate_legacy_signature(
    track_id: Union[int, str],
    format_id: Union[int, str],
    request_ts: Union[int, str],
    app_secret: str,
) -> str:
    """
    Alternative signature calculation without intent parameter.
    Used as fallback by some Qobuz endpoints.
    """
    sig_raw = (
        f"trackgetFileUrl"
        f"format_id{format_id}"
        f"track_id{track_id}"
        f"{request_ts}"
        f"{app_secret}"
    )
    return hashlib.md5(sig_raw.encode("utf-8")).hexdigest()
