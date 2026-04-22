"""
Navigation data retrieval: fetches Complete AIXM dataset via NM B2B (Redis pub/sub),
parses file ids from CompleteAIXMDatasetReply, then fetches each file via Redis
using JSON b2b.file_req (url) / b2b.file.data (base64). Saves only the feature types
needed for interpreting commercial aircraft routes: DesignatedPoint, Navaid, Route,
RouteSegment, AirportHeliport (and optionally AirportHeliportCollocation).

Usage:
  Set REDIS_*, END_USER_ID (and optionally AIRAC/date) below, then run:
  python navigation_data_retrieval.py
"""
import base64
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime

import redis

# --- Configuration ---
REDIS_HOST = "10.15.2.203"
REDIS_PORT = 6379
END_USER_ID = "lukasm"
REQUEST_CHANNEL = f"css:b2b:req:{END_USER_ID}:1"
REPLY_CHANNEL = f"css:b2b:rep:{END_USER_ID}:1"
RESPONSE_TIMEOUT = 90  # seconds for CompleteAIXMDatasetReply

# CompleteAIXMDataset query: optional. If all None, request is sent without queryCriteria.
QUERY_AIRAC_SEQUENCE_NUMBER = None  # e.g. 380
QUERY_AIRAC_ID = None  # e.g. "2402" for AIRAC 2024/02
QUERY_DATE = None  # "YYYY-MM-DD" for CompleteDatasetQueryCriteria.date

# File fetch via Redis (file_req)
FILE_FETCH_TIMEOUT = 10  # seconds per file
OUTPUT_DIR = "navigation_data"

# Feature types to download (AIXM feature type name as in file id, e.g. .../Navaid.BASELINE.zip)
FEATURE_TYPES = [
    "DesignatedPoint",
    "Navaid",
    "Route",
    "RouteSegment",
    "AirportHeliport",
    "AirportHeliportCollocation",
]


def _local_name(tag):
    return tag.split("}")[-1] if tag and "}" in tag else (tag or "")


def build_complete_aixm_request():
    """Build non-SOAP CompleteAIXMDatasetRequest XML."""
    query_criteria = ""
    if QUERY_AIRAC_SEQUENCE_NUMBER is not None:
        query_criteria = f"""    <queryCriteria>
        <airac>
            <airacSequenceNumber>{QUERY_AIRAC_SEQUENCE_NUMBER}</airacSequenceNumber>
        </airac>
    </queryCriteria>"""
    elif QUERY_AIRAC_ID is not None:
        query_criteria = f"""    <queryCriteria>
        <airac>
            <airacId>{QUERY_AIRAC_ID}</airacId>
        </airac>
    </queryCriteria>"""
    elif QUERY_DATE is not None:
        query_criteria = f"""    <queryCriteria>
        <date>{QUERY_DATE}</date>
    </queryCriteria>"""

    return f"""<?xml version="1.0"?>
<as:CompleteAIXMDatasetRequest xmlns:as="eurocontrol/cfmu/b2b/AirspaceServices" xmlns:cm="eurocontrol/cfmu/b2b/CommonServices">
    <endUserId>{END_USER_ID}</endUserId>
    <sendTime>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</sendTime>
{query_criteria}
</as:CompleteAIXMDatasetRequest>
"""


def parse_complete_aixm_reply(xml_bytes_or_str):
    """
    Parse CompleteAIXMDatasetReply XML.
    Returns (status_ok, list of (file_id, update_id)).
    update_id is from the parent datasetSummary for unique filenames.
    """
    if isinstance(xml_bytes_or_str, bytes):
        xml_bytes_or_str = xml_bytes_or_str.decode("utf-8")
    try:
        root = ET.fromstring(xml_bytes_or_str)
    except ET.ParseError:
        return False, []

    status_ok = False
    for el in root.iter():
        if _local_name(el.tag) == "status" and el.text and el.text.strip().upper() == "OK":
            status_ok = True
            break

    results = []
    for ds in root.iter():
        if _local_name(ds.tag) != "datasetSummaries":
            continue
        update_id = None
        for child in ds:
            if _local_name(child.tag) == "updateId" and child.text and child.text.strip().isdigit():
                update_id = int(child.text.strip())
                break
        for child in ds:
            if _local_name(child.tag) == "files":
                file_id = None
                for sub in child:
                    if _local_name(sub.tag) == "id" and sub.text and sub.text.strip():
                        file_id = sub.text.strip()
                        break
                if file_id:
                    results.append((file_id, update_id))
    return status_ok, results


def extract_feature_type_from_file_id(file_id):
    """Extract feature type from file id like AIXMFile/20141231/CDS_100/27.0.0/AirportHeliport.BASELINE.zip."""
    parts = file_id.split("/")
    if not parts:
        return None
    last = parts[-1]
    if last.endswith(".BASELINE.zip"):
        return last[: -len(".BASELINE.zip")]
    if last.endswith(".PERM_DELTA.zip"):
        return last[: -len(".PERM_DELTA.zip")]
    return None


def filter_file_ids_by_feature_types(file_id_list, feature_types):
    """
    file_id_list: list of (file_id, update_id).
    Returns list of (file_id, update_id, feature_type) for those whose feature type is in feature_types.
    """
    wanted = set(feature_types)
    out = []
    for file_id, update_id in file_id_list:
        ft = extract_feature_type_from_file_id(file_id)
        if ft and ft in wanted:
            out.append((file_id, update_id, ft))
    return out


def safe_filename_for_file_id(file_id, update_id, feature_type):
    """Produce a unique filename; avoid overwrites when multiple datasets have same feature type."""
    return f"{feature_type}_CDS_{update_id}.zip"


def fetch_file_via_redis(r, p, file_id, update_id, feature_type, output_dir, timeout=10):
    """
    Fetch one file via Redis: send JSON b2b.file_req.url, receive JSON with b2b.file.data (base64).
    Returns (path, size) or (None, 0) on error.
    """
    payload = {"b2b": {"file_req": {"url": file_id}}}
    r.publish(REQUEST_CHANNEL, json.dumps(payload).encode("utf-8"))
    message = p.get_message(timeout=timeout)
    if message is None:
        print(f"  No reply for file {file_id}")
        return None, 0
    if not message.get("data"):
        print(f"  Empty reply data for {file_id}")
        return None, 0
    raw = message["data"]
    raw_str = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    try:
        result = json.loads(raw_str)
        zip_b64 = result["b2b"]["file"]["data"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"  Invalid JSON or missing b2b.file.data for {file_id}: {e}")
        return None, 0
    try:
        zip_bytes = base64.b64decode(zip_b64)
    except Exception as e:
        print(f"  Base64 decode error for {file_id}: {e}")
        return None, 0
    filename = safe_filename_for_file_id(file_id, update_id, feature_type)
    path = os.path.join(output_dir, filename)
    try:
        with open(path, "wb") as f:
            f.write(zip_bytes)
        return path, len(zip_bytes)
    except OSError as e:
        print(f"  I/O error saving {filename}: {e}")
        return None, 0


def main():
    print("Navigation data retrieval (Complete AIXM + file fetch via Redis)")
    print("Connecting to Redis...")
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
    p = r.pubsub()
    p.subscribe(REPLY_CHANNEL)
    p.get_message(timeout=0.1)

    request_xml = build_complete_aixm_request()
    print("Sending CompleteAIXMDatasetRequest...")
    r.publish(REQUEST_CHANNEL, request_xml.encode("utf-8"))

    message = p.get_message(timeout=RESPONSE_TIMEOUT)
    if message is None:
        print("No reply received within timeout.")
        return
    if not message.get("data"):
        print("Empty reply data.")
        return

    raw = message["data"]
    if isinstance(raw, bytes):
        raw_str = raw.decode("utf-8")
    else:
        raw_str = raw

    # Always show what was received
    print("--- Response ---")
    max_show = 20000
    if len(raw_str) <= max_show:
        print(raw_str)
    else:
        print(raw_str[:max_show])
        print(f"... (truncated, total {len(raw_str)} chars)")
    print("--- End response ---")

    status_ok, file_id_list = parse_complete_aixm_reply(raw)
    if not status_ok:
        print("Reply status was not OK. Raw reply (first 1500 chars):")
        print(raw_str[:1500])
        return
    if not file_id_list:
        print("No dataset summaries in reply.")
        return

    # Keep only the latest dataset (highest updateId) so we download a single set of files
    valid = [(fid, uid) for fid, uid in file_id_list if uid is not None]
    if not valid:
        print("No dataset summaries with updateId in reply.")
        return
    best_update_id = max(uid for _, uid in valid)
    file_id_list_single = [(fid, uid) for fid, uid in file_id_list if uid == best_update_id]
    print(f"Using single dataset (updateId={best_update_id}), {len(file_id_list_single)} file(s) in dataset.")

    filtered = filter_file_ids_by_feature_types(file_id_list_single, FEATURE_TYPES)
    if not filtered:
        print("No file ids matched requested feature types:", FEATURE_TYPES)
        print("Available file ids (first 20):")
        for fid, _ in file_id_list_single[:20]:
            print(" ", fid)
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Fetching {len(filtered)} file(s) via Redis to {OUTPUT_DIR}/ ...")

    downloaded = []
    for file_id, update_id, feature_type in filtered:
        path, size = fetch_file_via_redis(
            r, p, file_id, update_id, feature_type, OUTPUT_DIR, timeout=FILE_FETCH_TIMEOUT
        )
        if path:
            downloaded.append((path, size))
            print(f"  Saved {path} ({size} bytes)")

    print("Done.")
    if downloaded:
        print("Downloaded files:")
        for path, size in downloaded:
            print(f"  {path}  ({size} bytes)")


if __name__ == "__main__":
    main()
