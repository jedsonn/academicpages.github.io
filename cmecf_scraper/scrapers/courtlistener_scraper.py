"""
CourtListener/RECAP Scraper for CM/ECF Implementation Dates.

Uses the Free Law Project's CourtListener API to find the earliest
electronic filings for each federal district court.

The earliest opinion/docket entry with electronic filing metadata
provides a hard lower bound on when CM/ECF was implemented.
"""

import re
import logging
from datetime import datetime, date
from typing import List, Optional, Dict, Any

try:
    from .base_scraper import BaseScraper
    from ..models.court_data import DateCandidate
except ImportError:
    from scrapers.base_scraper import BaseScraper
    from models.court_data import DateCandidate

logger = logging.getLogger(__name__)


class CourtListenerScraper(BaseScraper):
    """
    Scrapes CourtListener API for earliest electronic filings.

    CourtListener (courtlistener.com) is a free legal research platform
    maintained by the Free Law Project. It aggregates:
    - PACER docket data via RECAP
    - Court opinions
    - Oral arguments

    API Docs: https://www.courtlistener.com/api/rest-info/
    """

    # CourtListener API base URL
    API_BASE = "https://www.courtlistener.com/api/rest/v3"

    # Mapping of our court IDs to CourtListener court identifiers
    # CourtListener uses specific court slugs
    COURT_ID_MAP = {
        # First Circuit
        'mad': 'mad',   # D. Mass.
        'nhd': 'nhd',   # D.N.H.
        'rid': 'rid',   # D.R.I.
        'med': 'med',   # D. Me.
        'prd': 'prd',   # D.P.R.

        # Second Circuit
        'nysd': 'nysd', # S.D.N.Y.
        'nyed': 'nyed', # E.D.N.Y.
        'nynd': 'nynd', # N.D.N.Y.
        'nywd': 'nywd', # W.D.N.Y.
        'ctd': 'ctd',   # D. Conn.
        'vtd': 'vtd',   # D. Vt.

        # Third Circuit
        'paed': 'paed', # E.D. Pa.
        'pawd': 'pawd', # W.D. Pa.
        'pamd': 'pamd', # M.D. Pa.
        'njd': 'njd',   # D.N.J.
        'ded': 'ded',   # D. Del.
        'vid': 'vid',   # D.V.I.

        # Fourth Circuit
        'mdd': 'mdd',   # D. Md.
        'vaed': 'vaed', # E.D. Va.
        'vawd': 'vawd', # W.D. Va.
        'wvnd': 'wvnd', # N.D. W.Va.
        'wvsd': 'wvsd', # S.D. W.Va.
        'ncwd': 'ncwd', # W.D.N.C.
        'nced': 'nced', # E.D.N.C.
        'ncmd': 'ncmd', # M.D.N.C.
        'scd': 'scd',   # D.S.C.

        # Fifth Circuit
        'txnd': 'txnd', # N.D. Tex.
        'txsd': 'txsd', # S.D. Tex.
        'txed': 'txed', # E.D. Tex.
        'txwd': 'txwd', # W.D. Tex.
        'laed': 'laed', # E.D. La.
        'lawd': 'lawd', # W.D. La.
        'lamd': 'lamd', # M.D. La.
        'msnd': 'msnd', # N.D. Miss.
        'mssd': 'mssd', # S.D. Miss.

        # Sixth Circuit
        'mied': 'mied', # E.D. Mich.
        'miwd': 'miwd', # W.D. Mich.
        'ohnd': 'ohnd', # N.D. Ohio
        'ohsd': 'ohsd', # S.D. Ohio
        'kywd': 'kywd', # W.D. Ky.
        'kyed': 'kyed', # E.D. Ky.
        'tned': 'tned', # E.D. Tenn.
        'tnwd': 'tnwd', # W.D. Tenn.
        'tnmd': 'tnmd', # M.D. Tenn.

        # Seventh Circuit
        'ilnd': 'ilnd', # N.D. Ill.
        'ilcd': 'ilcd', # C.D. Ill.
        'ilsd': 'ilsd', # S.D. Ill.
        'innd': 'innd', # N.D. Ind.
        'insd': 'insd', # S.D. Ind.
        'wied': 'wied', # E.D. Wis.
        'wiwd': 'wiwd', # W.D. Wis.

        # Eighth Circuit
        'moed': 'moed', # E.D. Mo.
        'mowd': 'mowd', # W.D. Mo.
        'ared': 'ared', # E.D. Ark.
        'arwd': 'arwd', # W.D. Ark.
        'iand': 'iand', # N.D. Iowa
        'iasd': 'iasd', # S.D. Iowa
        'mnd': 'mnd',   # D. Minn.
        'ned': 'ned',   # D. Neb.
        'ndd': 'ndd',   # D.N.D.
        'sdd': 'sdd',   # D.S.D.

        # Ninth Circuit
        'cand': 'cand', # N.D. Cal.
        'cacd': 'cacd', # C.D. Cal.
        'casd': 'casd', # S.D. Cal.
        'caed': 'caed', # E.D. Cal.
        'azd': 'azd',   # D. Ariz.
        'nvd': 'nvd',   # D. Nev.
        'ord': 'ord',   # D. Or.
        'waed': 'waed', # E.D. Wash.
        'wawd': 'wawd', # W.D. Wash.
        'idd': 'idd',   # D. Idaho
        'mtd': 'mtd',   # D. Mont.
        'akd': 'akd',   # D. Alaska
        'hid': 'hid',   # D. Haw.
        'gud': 'gud',   # D. Guam
        'nmid': 'nmid', # D.N.M.I.

        # Tenth Circuit
        'cod': 'cod',   # D. Colo.
        'ksd': 'ksd',   # D. Kan.
        'nmd': 'nmd',   # D.N.M.
        'oknd': 'oknd', # N.D. Okla.
        'oked': 'oked', # E.D. Okla.
        'okwd': 'okwd', # W.D. Okla.
        'utd': 'utd',   # D. Utah
        'wyd': 'wyd',   # D. Wyo.

        # Eleventh Circuit
        'flnd': 'flnd', # N.D. Fla.
        'flmd': 'flmd', # M.D. Fla.
        'flsd': 'flsd', # S.D. Fla.
        'gand': 'gand', # N.D. Ga.
        'gamd': 'gamd', # M.D. Ga.
        'gasd': 'gasd', # S.D. Ga.
        'alnd': 'alnd', # N.D. Ala.
        'almd': 'almd', # M.D. Ala.
        'alsd': 'alsd', # S.D. Ala.

        # DC Circuit
        'dcd': 'dcd',   # D.D.C.
    }

    def __init__(self, config: dict):
        super().__init__(config)
        # CourtListener API is free but rate-limited
        self.headers = {
            'User-Agent': 'CMECFDateScraper/1.0 (Academic Research)',
        }

    def scrape(self, court_id: str, court_info: dict) -> List[DateCandidate]:
        """
        Query CourtListener for earliest electronic filings.

        Args:
            court_id: Court identifier (e.g., 'nysd')
            court_info: Court metadata

        Returns:
            List of DateCandidate objects with earliest filing dates
        """
        candidates = []

        cl_court_id = self.COURT_ID_MAP.get(court_id, court_id)
        court_name = court_info.get('name', court_id)

        logger.info(f"Querying CourtListener for {court_name} earliest filings")

        # Strategy 1: Find earliest opinion
        earliest_opinion = self._get_earliest_opinion(cl_court_id)
        if earliest_opinion:
            candidates.append(earliest_opinion)

        # Strategy 2: Find earliest docket entry
        earliest_docket = self._get_earliest_docket(cl_court_id)
        if earliest_docket:
            candidates.append(earliest_docket)

        # Strategy 3: Find earliest RECAP document
        earliest_recap = self._get_earliest_recap_doc(cl_court_id)
        if earliest_recap:
            candidates.append(earliest_recap)

        return candidates

    def _get_earliest_opinion(self, court_id: str) -> Optional[DateCandidate]:
        """
        Get the earliest opinion from CourtListener for a court.

        Uses the opinions endpoint sorted by date ascending.
        """
        url = f"{self.API_BASE}/opinions/"
        params = {
            'court': court_id,
            'order_by': 'date_filed',
            'page_size': 1,
        }

        try:
            response = self._make_request(url, params=params)
            if response and response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    result = data['results'][0]
                    date_str = result.get('date_filed')
                    if date_str:
                        filing_date = datetime.strptime(date_str, '%Y-%m-%d').date()

                        # Only consider as CM/ECF indicator if after 1996
                        if filing_date.year >= 1996:
                            return DateCandidate(
                                date=filing_date,
                                confidence=2.5,  # Lower confidence - this is a lower bound
                                source_type="courtlistener_opinion",
                                source_url=f"https://www.courtlistener.com{result.get('absolute_url', '')}",
                                context=f"Earliest CourtListener opinion: {result.get('case_name', 'Unknown')[:50]}",
                                extraction_method="api_earliest_filing"
                            )
        except Exception as e:
            logger.debug(f"CourtListener opinion query failed for {court_id}: {e}")

        return None

    def _get_earliest_docket(self, court_id: str) -> Optional[DateCandidate]:
        """
        Get the earliest docket from CourtListener's RECAP archive.

        RECAP documents are sourced from PACER, so they represent
        actual electronic filings.
        """
        url = f"{self.API_BASE}/dockets/"
        params = {
            'court': court_id,
            'order_by': 'date_filed',
            'page_size': 1,
            'source__in': '1,2,4',  # RECAP sources
        }

        try:
            response = self._make_request(url, params=params)
            if response and response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    result = data['results'][0]
                    date_str = result.get('date_filed')
                    if date_str:
                        filing_date = datetime.strptime(date_str, '%Y-%m-%d').date()

                        if filing_date.year >= 1996:
                            return DateCandidate(
                                date=filing_date,
                                confidence=3.0,  # Medium confidence - actual PACER filing
                                source_type="courtlistener_docket",
                                source_url=f"https://www.courtlistener.com{result.get('absolute_url', '')}",
                                context=f"Earliest RECAP docket: {result.get('case_name', 'Unknown')[:50]}",
                                extraction_method="api_earliest_filing"
                            )
        except Exception as e:
            logger.debug(f"CourtListener docket query failed for {court_id}: {e}")

        return None

    def _get_earliest_recap_doc(self, court_id: str) -> Optional[DateCandidate]:
        """
        Get the earliest RECAP document for a court.

        RECAP documents have upload dates which can indicate when
        electronic filing was available.
        """
        url = f"{self.API_BASE}/recap-documents/"
        params = {
            'court': court_id,
            'order_by': 'date_upload',
            'page_size': 1,
            'is_available': True,
        }

        try:
            response = self._make_request(url, params=params)
            if response and response.status_code == 200:
                data = response.json()
                if data.get('results'):
                    result = data['results'][0]
                    # Try date_filed first, then date_upload
                    date_str = result.get('date_filed') or result.get('date_upload', '')[:10]
                    if date_str:
                        try:
                            filing_date = datetime.strptime(date_str[:10], '%Y-%m-%d').date()

                            if filing_date.year >= 1996:
                                return DateCandidate(
                                    date=filing_date,
                                    confidence=3.5,  # Higher confidence - actual uploaded doc
                                    source_type="courtlistener_recap",
                                    source_url=f"https://www.courtlistener.com/docket/{result.get('docket', '')}/",
                                    context=f"Earliest RECAP document upload",
                                    extraction_method="api_earliest_filing"
                                )
                        except ValueError:
                            pass
        except Exception as e:
            logger.debug(f"CourtListener RECAP query failed for {court_id}: {e}")

        return None

    def get_filing_statistics(self, court_id: str) -> Dict[str, Any]:
        """
        Get filing statistics to help infer CM/ECF implementation.

        A sudden increase in available documents often indicates
        when electronic filing became mandatory.
        """
        cl_court_id = self.COURT_ID_MAP.get(court_id, court_id)
        stats = {
            'court_id': court_id,
            'earliest_opinion': None,
            'earliest_docket': None,
            'total_dockets': 0,
        }

        # Get count of dockets
        url = f"{self.API_BASE}/dockets/"
        params = {
            'court': cl_court_id,
            'page_size': 1,
        }

        try:
            response = self._make_request(url, params=params)
            if response and response.status_code == 200:
                data = response.json()
                stats['total_dockets'] = data.get('count', 0)
        except Exception as e:
            logger.debug(f"Stats query failed: {e}")

        return stats
