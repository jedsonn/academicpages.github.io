"""
Configuration for CM/ECF scraper.
Contains all 94 district courts and scraping settings.
"""

import os
from pathlib import Path
from typing import Dict, Any

# Get the directory of this config file
_SCRIPT_DIR = Path(__file__).parent

# Rate limiting configuration
RATE_LIMIT_DELAY = 0.1  # seconds between requests to same domain (fast for blocked networks)
MAX_RETRIES = 1  # Single try for blocked networks
RETRY_BACKOFF = 1  # exponential backoff multiplier
REQUEST_TIMEOUT = 3  # seconds - short timeout for blocked networks

# Wayback Machine settings
WAYBACK_API_URL = "https://web.archive.org/cdx/search/cdx"
WAYBACK_SNAPSHOT_URL = "https://web.archive.org/web"

# Date range for CM/ECF implementation
MIN_YEAR = 1996  # Earliest pilot programs
MAX_YEAR = 2008  # All courts should be live by then

# Confidence scoring
CONFIDENCE_LEVELS = {
    5: "exact_date_official_source",
    4: "exact_date_secondary_source",
    3: "month_precision",
    2: "quarter_or_year_precision",
    1: "inferred_from_pacer"
}

# Keywords to search for CM/ECF implementation dates
CMECF_KEYWORDS = [
    "CM/ECF",
    "CM-ECF",
    "CMECF",
    "Case Management/Electronic Case Files",
    "electronic case filing",
    "electronic filing",
    "e-filing",
    "efiling",
    "ECF system"
]

IMPLEMENTATION_KEYWORDS = [
    "began",
    "implemented",
    "launched",
    "went live",
    "started",
    "effective",
    "go-live",
    "rollout",
    "deployed",
    "activated",
    "introduced",
    "adopted"
]

# Pages to check on each court website (reduced list for faster scraping)
COURT_PAGES_TO_CHECK = [
    "",  # homepage
    "/cmecf",
    "/cm-ecf",
    "/electronic-filing",
    # "/ecf",
    # "/efiling",
    # "/e-filing",
    # "/case-info",
    # "/case-information",
    # "/attorneys",
    # "/attorney-information",
    # "/court-info",
    # "/about-the-court",
    # "/about",
    # "/news",
    # "/announcements",
    # "/general-orders",
    # "/orders/general-orders",
    # "/administrative-orders",
    # "/orders/administrative-orders",
    # "/local-rules",
    # "/standing-orders",
    # "/clerk",
    # "/clerks-office",
    # "/filing",
    # "/filing-procedures",
    # "/history",
    # "/court-history"
]

# PDF order patterns to look for
PDF_ORDER_PATTERNS = [
    "general order",
    "administrative order",
    "standing order",
    "electronic case filing",
    "ecf procedures",
    "cm/ecf"
]

# All 94 U.S. District Courts
DISTRICT_COURTS: Dict[str, Dict[str, Any]] = {
    # First Circuit
    "mad": {"name": "District of Massachusetts", "circuit": 1, "state": "MA", "url": "https://www.mad.uscourts.gov"},
    "med": {"name": "District of Maine", "circuit": 1, "state": "ME", "url": "https://www.med.uscourts.gov"},
    "nhd": {"name": "District of New Hampshire", "circuit": 1, "state": "NH", "url": "https://www.nhd.uscourts.gov"},
    "prd": {"name": "District of Puerto Rico", "circuit": 1, "state": "PR", "url": "https://www.prd.uscourts.gov"},
    "rid": {"name": "District of Rhode Island", "circuit": 1, "state": "RI", "url": "https://www.rid.uscourts.gov"},

    # Second Circuit
    "ctd": {"name": "District of Connecticut", "circuit": 2, "state": "CT", "url": "https://www.ctd.uscourts.gov"},
    "nyed": {"name": "Eastern District of New York", "circuit": 2, "state": "NY", "url": "https://www.nyed.uscourts.gov"},
    "nynd": {"name": "Northern District of New York", "circuit": 2, "state": "NY", "url": "https://www.nynd.uscourts.gov"},
    "nysd": {"name": "Southern District of New York", "circuit": 2, "state": "NY", "url": "https://www.nysd.uscourts.gov"},
    "nywd": {"name": "Western District of New York", "circuit": 2, "state": "NY", "url": "https://www.nywd.uscourts.gov"},
    "vtd": {"name": "District of Vermont", "circuit": 2, "state": "VT", "url": "https://www.vtd.uscourts.gov"},

    # Third Circuit
    "ded": {"name": "District of Delaware", "circuit": 3, "state": "DE", "url": "https://www.ded.uscourts.gov"},
    "njd": {"name": "District of New Jersey", "circuit": 3, "state": "NJ", "url": "https://www.njd.uscourts.gov"},
    "paed": {"name": "Eastern District of Pennsylvania", "circuit": 3, "state": "PA", "url": "https://www.paed.uscourts.gov"},
    "pamd": {"name": "Middle District of Pennsylvania", "circuit": 3, "state": "PA", "url": "https://www.pamd.uscourts.gov"},
    "pawd": {"name": "Western District of Pennsylvania", "circuit": 3, "state": "PA", "url": "https://www.pawd.uscourts.gov"},
    "vid": {"name": "District of the Virgin Islands", "circuit": 3, "state": "VI", "url": "https://www.vid.uscourts.gov"},

    # Fourth Circuit
    "mdd": {"name": "District of Maryland", "circuit": 4, "state": "MD", "url": "https://www.mdd.uscourts.gov"},
    "nced": {"name": "Eastern District of North Carolina", "circuit": 4, "state": "NC", "url": "https://www.nced.uscourts.gov"},
    "ncmd": {"name": "Middle District of North Carolina", "circuit": 4, "state": "NC", "url": "https://www.ncmd.uscourts.gov"},
    "ncwd": {"name": "Western District of North Carolina", "circuit": 4, "state": "NC", "url": "https://www.ncwd.uscourts.gov"},
    "scd": {"name": "District of South Carolina", "circuit": 4, "state": "SC", "url": "https://www.scd.uscourts.gov"},
    "vaed": {"name": "Eastern District of Virginia", "circuit": 4, "state": "VA", "url": "https://www.vaed.uscourts.gov"},
    "vawd": {"name": "Western District of Virginia", "circuit": 4, "state": "VA", "url": "https://www.vawd.uscourts.gov"},
    "wvnd": {"name": "Northern District of West Virginia", "circuit": 4, "state": "WV", "url": "https://www.wvnd.uscourts.gov"},
    "wvsd": {"name": "Southern District of West Virginia", "circuit": 4, "state": "WV", "url": "https://www.wvsd.uscourts.gov"},

    # Fifth Circuit
    "laed": {"name": "Eastern District of Louisiana", "circuit": 5, "state": "LA", "url": "https://www.laed.uscourts.gov"},
    "lamd": {"name": "Middle District of Louisiana", "circuit": 5, "state": "LA", "url": "https://www.lamd.uscourts.gov"},
    "lawd": {"name": "Western District of Louisiana", "circuit": 5, "state": "LA", "url": "https://www.lawd.uscourts.gov"},
    "msnd": {"name": "Northern District of Mississippi", "circuit": 5, "state": "MS", "url": "https://www.msnd.uscourts.gov"},
    "mssd": {"name": "Southern District of Mississippi", "circuit": 5, "state": "MS", "url": "https://www.mssd.uscourts.gov"},
    "txed": {"name": "Eastern District of Texas", "circuit": 5, "state": "TX", "url": "https://www.txed.uscourts.gov"},
    "txnd": {"name": "Northern District of Texas", "circuit": 5, "state": "TX", "url": "https://www.txnd.uscourts.gov"},
    "txsd": {"name": "Southern District of Texas", "circuit": 5, "state": "TX", "url": "https://www.txsd.uscourts.gov"},
    "txwd": {"name": "Western District of Texas", "circuit": 5, "state": "TX", "url": "https://www.txwd.uscourts.gov"},

    # Sixth Circuit
    "kyed": {"name": "Eastern District of Kentucky", "circuit": 6, "state": "KY", "url": "https://www.kyed.uscourts.gov"},
    "kywd": {"name": "Western District of Kentucky", "circuit": 6, "state": "KY", "url": "https://www.kywd.uscourts.gov"},
    "mied": {"name": "Eastern District of Michigan", "circuit": 6, "state": "MI", "url": "https://www.mied.uscourts.gov"},
    "miwd": {"name": "Western District of Michigan", "circuit": 6, "state": "MI", "url": "https://www.miwd.uscourts.gov"},
    "ohnd": {"name": "Northern District of Ohio", "circuit": 6, "state": "OH", "url": "https://www.ohnd.uscourts.gov"},
    "ohsd": {"name": "Southern District of Ohio", "circuit": 6, "state": "OH", "url": "https://www.ohsd.uscourts.gov"},
    "tned": {"name": "Eastern District of Tennessee", "circuit": 6, "state": "TN", "url": "https://www.tned.uscourts.gov"},
    "tnmd": {"name": "Middle District of Tennessee", "circuit": 6, "state": "TN", "url": "https://www.tnmd.uscourts.gov"},
    "tnwd": {"name": "Western District of Tennessee", "circuit": 6, "state": "TN", "url": "https://www.tnwd.uscourts.gov"},

    # Seventh Circuit
    "ilcd": {"name": "Central District of Illinois", "circuit": 7, "state": "IL", "url": "https://www.ilcd.uscourts.gov"},
    "ilnd": {"name": "Northern District of Illinois", "circuit": 7, "state": "IL", "url": "https://www.ilnd.uscourts.gov"},
    "ilsd": {"name": "Southern District of Illinois", "circuit": 7, "state": "IL", "url": "https://www.ilsd.uscourts.gov"},
    "innd": {"name": "Northern District of Indiana", "circuit": 7, "state": "IN", "url": "https://www.innd.uscourts.gov"},
    "insd": {"name": "Southern District of Indiana", "circuit": 7, "state": "IN", "url": "https://www.insd.uscourts.gov"},
    "wied": {"name": "Eastern District of Wisconsin", "circuit": 7, "state": "WI", "url": "https://www.wied.uscourts.gov"},
    "wiwd": {"name": "Western District of Wisconsin", "circuit": 7, "state": "WI", "url": "https://www.wiwd.uscourts.gov"},

    # Eighth Circuit
    "ared": {"name": "Eastern District of Arkansas", "circuit": 8, "state": "AR", "url": "https://www.ared.uscourts.gov"},
    "arwd": {"name": "Western District of Arkansas", "circuit": 8, "state": "AR", "url": "https://www.arwd.uscourts.gov"},
    "iasd": {"name": "Southern District of Iowa", "circuit": 8, "state": "IA", "url": "https://www.iasd.uscourts.gov"},
    "iand": {"name": "Northern District of Iowa", "circuit": 8, "state": "IA", "url": "https://www.iand.uscourts.gov"},
    "mnd": {"name": "District of Minnesota", "circuit": 8, "state": "MN", "url": "https://www.mnd.uscourts.gov"},
    "moed": {"name": "Eastern District of Missouri", "circuit": 8, "state": "MO", "url": "https://www.moed.uscourts.gov"},
    "mowd": {"name": "Western District of Missouri", "circuit": 8, "state": "MO", "url": "https://www.mowd.uscourts.gov"},
    "ned": {"name": "District of Nebraska", "circuit": 8, "state": "NE", "url": "https://www.ned.uscourts.gov"},
    "ndd": {"name": "District of North Dakota", "circuit": 8, "state": "ND", "url": "https://www.ndd.uscourts.gov"},
    "sdd": {"name": "District of South Dakota", "circuit": 8, "state": "SD", "url": "https://www.sdd.uscourts.gov"},

    # Ninth Circuit
    "akd": {"name": "District of Alaska", "circuit": 9, "state": "AK", "url": "https://www.akd.uscourts.gov"},
    "azd": {"name": "District of Arizona", "circuit": 9, "state": "AZ", "url": "https://www.azd.uscourts.gov"},
    "cacd": {"name": "Central District of California", "circuit": 9, "state": "CA", "url": "https://www.cacd.uscourts.gov"},
    "caed": {"name": "Eastern District of California", "circuit": 9, "state": "CA", "url": "https://www.caed.uscourts.gov"},
    "cand": {"name": "Northern District of California", "circuit": 9, "state": "CA", "url": "https://www.cand.uscourts.gov"},
    "casd": {"name": "Southern District of California", "circuit": 9, "state": "CA", "url": "https://www.casd.uscourts.gov"},
    "gud": {"name": "District of Guam", "circuit": 9, "state": "GU", "url": "https://www.gud.uscourts.gov"},
    "hid": {"name": "District of Hawaii", "circuit": 9, "state": "HI", "url": "https://www.hid.uscourts.gov"},
    "idd": {"name": "District of Idaho", "circuit": 9, "state": "ID", "url": "https://www.idd.uscourts.gov"},
    "mtd": {"name": "District of Montana", "circuit": 9, "state": "MT", "url": "https://www.mtd.uscourts.gov"},
    "nvd": {"name": "District of Nevada", "circuit": 9, "state": "NV", "url": "https://www.nvd.uscourts.gov"},
    "nmid": {"name": "District of Northern Mariana Islands", "circuit": 9, "state": "MP", "url": "https://www.nmid.uscourts.gov"},
    "ord": {"name": "District of Oregon", "circuit": 9, "state": "OR", "url": "https://www.ord.uscourts.gov"},
    "waed": {"name": "Eastern District of Washington", "circuit": 9, "state": "WA", "url": "https://www.waed.uscourts.gov"},
    "wawd": {"name": "Western District of Washington", "circuit": 9, "state": "WA", "url": "https://www.wawd.uscourts.gov"},

    # Tenth Circuit
    "cod": {"name": "District of Colorado", "circuit": 10, "state": "CO", "url": "https://www.cod.uscourts.gov"},
    "ksd": {"name": "District of Kansas", "circuit": 10, "state": "KS", "url": "https://www.ksd.uscourts.gov"},
    "nmd": {"name": "District of New Mexico", "circuit": 10, "state": "NM", "url": "https://www.nmd.uscourts.gov"},
    "oked": {"name": "Eastern District of Oklahoma", "circuit": 10, "state": "OK", "url": "https://www.oked.uscourts.gov"},
    "oknd": {"name": "Northern District of Oklahoma", "circuit": 10, "state": "OK", "url": "https://www.oknd.uscourts.gov"},
    "okwd": {"name": "Western District of Oklahoma", "circuit": 10, "state": "OK", "url": "https://www.okwd.uscourts.gov"},
    "utd": {"name": "District of Utah", "circuit": 10, "state": "UT", "url": "https://www.utd.uscourts.gov"},
    "wyd": {"name": "District of Wyoming", "circuit": 10, "state": "WY", "url": "https://www.wyd.uscourts.gov"},

    # Eleventh Circuit
    "almd": {"name": "Middle District of Alabama", "circuit": 11, "state": "AL", "url": "https://www.almd.uscourts.gov"},
    "alnd": {"name": "Northern District of Alabama", "circuit": 11, "state": "AL", "url": "https://www.alnd.uscourts.gov"},
    "alsd": {"name": "Southern District of Alabama", "circuit": 11, "state": "AL", "url": "https://www.alsd.uscourts.gov"},
    "flmd": {"name": "Middle District of Florida", "circuit": 11, "state": "FL", "url": "https://www.flmd.uscourts.gov"},
    "flnd": {"name": "Northern District of Florida", "circuit": 11, "state": "FL", "url": "https://www.flnd.uscourts.gov"},
    "flsd": {"name": "Southern District of Florida", "circuit": 11, "state": "FL", "url": "https://www.flsd.uscourts.gov"},
    "gamd": {"name": "Middle District of Georgia", "circuit": 11, "state": "GA", "url": "https://www.gamd.uscourts.gov"},
    "gand": {"name": "Northern District of Georgia", "circuit": 11, "state": "GA", "url": "https://www.gand.uscourts.gov"},
    "gasd": {"name": "Southern District of Georgia", "circuit": 11, "state": "GA", "url": "https://www.gasd.uscourts.gov"},

    # D.C. Circuit
    "dcd": {"name": "District of Columbia", "circuit": "DC", "state": "DC", "url": "https://www.dcd.uscourts.gov"},
}

# Known reference points for validation
# Sources: Wikipedia CM/ECF article, court websites, FJC records, web research
KNOWN_DATES = {
    # Early pilots (1996-1997)
    "ohnd": {"date": "1996", "precision": "year", "notes": "First pilot - asbestos cases"},
    "mowd": {"date": "1997", "precision": "year", "notes": "Late 1997 pilot"},
    "nyed": {"date": "1997", "precision": "year", "notes": "Late 1997 pilot"},
    "ord": {"date": "1997", "precision": "year", "notes": "Late 1997 pilot"},

    # National rollout began May 2002
    "cand": {"date": "2001-04-02", "precision": "exact", "notes": "Pilot April 2, 2001; Full January 1, 2003"},
    "flsd": {"date": "2002", "precision": "year", "notes": "Local system 2002, mandatory 2004"},

    # 2003 implementations
    "sdd": {"date": "2003-07-03", "precision": "exact", "notes": "CM/ECF went live per court website"},
    "mad": {"date": "2003-10-01", "precision": "exact", "notes": "Local Rule 5.4 electronic filing"},
    "okwd": {"date": "2003-10-14", "precision": "exact", "notes": "Document scanning began"},
    "nysd": {"date": "2003-12-02", "precision": "exact", "notes": "New civil and criminal cases assigned to ECF"},

    # Later implementations
    "mied": {"date": "2005-11-30", "precision": "exact", "notes": ""},
}

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Logging configuration
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
LOG_FILE = str(_SCRIPT_DIR / "output" / "scraping_log.txt")
