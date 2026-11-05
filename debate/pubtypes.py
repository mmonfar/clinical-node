"""Publication types from NCBI E-utilities esummary (SPEC section 4, level of evidence).

Research and demonstration software. Not a medical device. Synthetic cases only.
Plain urllib, no Biopython, no API key, no email. One request per batch of PMIDs.
NCBI allows 3 requests per second without a key: we wait at least 0.34 s between requests.
No tool/email parameter is sent: the repo has no non-personal one, and the personal one is never used.
"""
import json
import re
import time
import urllib.parse
import urllib.request

ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
MIN_INTERVAL_S = 0.34   # under 3 requests per second
BATCH = 100
TIMEOUT_S = 15

_last = [0.0]


def _http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "clinical-node-research-demo"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 (fixed https host)
        return resp.read()


def fetch_pubtypes(pmids, http_get=None, sleep=time.sleep, clock=time.monotonic):
    """Return {pmid: [publication types]} for the PMIDs NCBI answers for.

    Raises on network or JSON errors (the caller turns that into 'level unknown').
    http_get(url) -> bytes is injectable so tests never touch the network.
    """
    get = http_get or _http_get
    ids = [p for p in dict.fromkeys(str(p) for p in pmids) if re.fullmatch(r"[0-9]+", p)]
    out = {}
    for i in range(0, len(ids), BATCH):
        wait = MIN_INTERVAL_S - (clock() - _last[0])
        if _last[0] and wait > 0:
            sleep(wait)
        _last[0] = clock()
        query = urllib.parse.urlencode({"db": "pubmed", "retmode": "json",
                                        "id": ",".join(ids[i:i + BATCH])})
        data = json.loads(get(f"{ESUMMARY_URL}?{query}"))
        result = data.get("result", {})
        for uid in result.get("uids", []):
            rec = result.get(uid, {})
            types = rec.get("pubtype", [])
            if isinstance(types, list):
                out[str(uid)] = [t for t in types if isinstance(t, str)]
    return out
