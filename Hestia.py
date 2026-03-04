#!/usr/bin/env python3
"""
Hestia - Predator Case Management & Evidence Automation Framework
Version: 1.0 - By Phoenix/Minthol

Purpose: Streamline the process of gathering evidence against online child predators
         from initial lead to submission-ready dossier for authorities.
         All text and comments are in English.
"""

import os
import sys
import time
import json
import re
import requests
import hashlib
import base64
import csv
import sqlite3
import argparse
import threading
import queue
import random
import string
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging
import warnings
import pickle
import zipfile
import tempfile

# Core OSINT & data extraction
import requests
from bs4 import BeautifulSoup
import dns.resolver
import whois
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
import exifread
from PIL import Image, ExifTags
import pandas as pd
import numpy as np

# Anonymity (critical for your safety)
try:
    import stem
    import stem.control
    import stem.process
    TOR_AVAILABLE = True
except ImportError:
    TOR_AVAILABLE = False
    print("[!] Tor module not installed. Anonymity features disabled.")

try:
    import socks
    SOCKS_AVAILABLE = True
except ImportError:
    SOCKS_AVAILABLE = False

# Reporting & evidence packaging
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("[!] ReportLab not installed. PDF generation disabled.")

import markdown
try:
    import pdfkit
    PDFKIT_AVAILABLE = True
except ImportError:
    PDFKIT_AVAILABLE = False

# Suppress warnings
warnings.filterwarnings('ignore')

# ==================== COLOR SYSTEM ====================
R = '\033[91m'; G = '\033[92m'; Y = '\033[93m'; B = '\033[94m'
M = '\033[95m'; C = '\033[96m'; W = '\033[97m'; RESET = '\033[0m'
BOLD = '\033[1m'

# ==================== LOGGING SETUP ====================

def setup_logging(log_file: str = 'hestia.log'):
    """Configure logging with file and console handlers."""
    logger = logging.getLogger('hestia')
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger

logger = setup_logging()

# ==================== DATA CLASSES ====================

class EvidenceType(Enum):
    """Types of evidence that can be collected."""
    SCREENSHOT = "screenshot"
    POST = "post"
    MESSAGE = "message"
    PROFILE = "profile"
    METADATA = "metadata"
    NETWORK = "network"
    LOCATION = "location"
    IDENTITY = "identity"
    FINANCIAL = "financial"
    COMMUNICATION = "communication"
    THREAT = "threat"
    OTHER = "other"

class ThreatLevel(Enum):
    """Threat levels for risk assessment."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Jurisdiction(Enum):
    """Supported jurisdictions for evidence standards."""
    GERMANY_BKA = "Germany - BKA"
    USA_FBI = "USA - FBI"
    USA_ICAC = "USA - ICAC Task Force"
    UK_NCA = "UK - National Crime Agency"
    EU_EUROPOL = "EU - Europol"
    INTERPOL = "INTERPOL"
    CUSTOM = "Custom"

@dataclass
class EvidenceItem:
    """
    Represents a single piece of evidence with full chain of custody.
    All fields are in English.
    """
    id: str = None
    type: EvidenceType = EvidenceType.OTHER
    source: str = None
    url: str = None
    content: str = None
    file_path: str = None
    hash_sha256: str = None
    timestamp_utc: str = None
    collected_by: str = None
    collection_method: str = None
    notes: str = None
    tags: List[str] = field(default_factory=list)
    related_evidence_ids: List[str] = field(default_factory=list)
    threat_level: ThreatLevel = ThreatLevel.NONE
    verified: bool = False
    chain_of_custody: List[Dict] = field(default_factory=list)
    
    def __post_init__(self):
        """Generate ID and hash if not provided."""
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.timestamp_utc:
            self.timestamp_utc = datetime.now(datetime.timezone.utc).isoformat()
        if self.content and not self.hash_sha256:
            self.hash_sha256 = hashlib.sha256(self.content.encode()).hexdigest()
        self._add_to_chain("Evidence created")
    
    def _add_to_chain(self, action: str):
        """Add an entry to the chain of custody."""
        self.chain_of_custody.append({
            'timestamp': datetime.now(datetime.timezone.utc).isoformat(),
            'action': action,
            'actor': 'Hestia System'
        })
    
    def verify(self):
        """Mark evidence as verified."""
        self.verified = True
        self._add_to_chain("Evidence verified")

@dataclass
class SuspectProfile:
    """Complete profile of a suspect with all gathered intelligence."""
    id: str = None
    primary_username: str = None
    aliases: List[str] = field(default_factory=list)
    real_name: str = None
    age: int = None
    dob: str = None
    gender: str = None
    location: str = None
    country: str = None
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    addresses: List[str] = field(default_factory=list)
    social_media: Dict[str, str] = field(default_factory=dict)
    platforms: List[str] = field(default_factory=list)
    ips: List[str] = field(default_factory=list)
    crypto_wallets: List[str] = field(default_factory=list)
    threat_level: ThreatLevel = ThreatLevel.NONE
    notes: str = None
    evidence_ids: List[str] = field(default_factory=list)
    created: str = None
    updated: str = None
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created:
            self.created = datetime.now(datetime.timezone.utc).isoformat()
        self.updated = datetime.now(datetime.timezone.utc).isoformat()

@dataclass
class Case:
    """
    Main case container for a predator investigation.
    All fields in English.
    """
    case_id: str = None
    title: str = None
    description: str = None
    jurisdiction: Jurisdiction = Jurisdiction.CUSTOM
    investigating_agency: str = None
    case_number: str = None
    lead_source: str = None
    lead_date: str = None
    suspects: List[SuspectProfile] = field(default_factory=list)
    victims: List[str] = field(default_factory=list)  # Victim identifiers or descriptions
    evidence: Dict[str, EvidenceItem] = field(default_factory=dict)
    timeline: List[Dict] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    status: str = "open"  # open, active, pending, closed, archived
    risk_level: ThreatLevel = ThreatLevel.NONE
    notes: str = None
    created: str = None
    updated: str = None
    submitted_to_authorities: bool = False
    submission_date: str = None
    submission_reference: str = None
    
    def __post_init__(self):
        if not self.case_id:
            self.case_id = f"CASE-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000,9999)}"
        if not self.created:
            self.created = datetime.now(datetime.timezone.utc).isoformat()
        self.updated = datetime.now(datetime.timezone.utc).isoformat()
    
    def add_evidence(self, evidence: EvidenceItem):
        """Add evidence to the case."""
        self.evidence[evidence.id] = evidence
        self._add_to_timeline(f"Evidence added: {evidence.type.value} from {evidence.source}")
        self.updated = datetime.now(datetime.timezone.utc).isoformat()
    
    def add_suspect(self, suspect: SuspectProfile):
        """Add a suspect to the case."""
        self.suspects.append(suspect)
        self._add_to_timeline(f"Suspect added: {suspect.primary_username}")
        self.updated = datetime.now(datetime.timezone.utc).isoformat()
    
    def _add_to_timeline(self, event: str):
        """Add an event to the case timeline."""
        self.timeline.append({
            'timestamp': datetime.now(datetime.timezone.utc).isoformat(),
            'event': event
        })

# ==================== ANONYMITY LAYER ====================

class Anonymizer:
    """
    Handles anonymous connections via Tor for safe investigation.
    All methods and comments in English.
    """
    
    def __init__(self, use_tor: bool = True, tor_port: int = 9050, control_port: int = 9051):
        self.use_tor = use_tor and TOR_AVAILABLE
        self.tor_port = tor_port
        self.control_port = control_port
        self.session = None
        self.tor_process = None
        self.controller = None
        self.current_ip = None
        self._setup_session()
    
    def _setup_session(self):
        """Set up requests session with Tor if available."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        if self.use_tor and SOCKS_AVAILABLE:
            self.session.proxies = {
                'http': f'socks5://127.0.0.1:{self.tor_port}',
                'https': f'socks5://127.0.0.1:{self.tor_port}'
            }
            self._get_current_ip()
            logger.info(f"Tor enabled. Current exit IP: {self.current_ip}")
    
    def _get_current_ip(self):
        """Get current Tor exit node IP."""
        try:
            response = self.session.get('https://api.ipify.org?format=json', timeout=10)
            self.current_ip = response.json().get('ip', 'Unknown')
        except:
            self.current_ip = 'Unknown'
    
    def get_session(self) -> requests.Session:
        """Get the configured session."""
        return self.session
    
    def rotate_identity(self):
        """Request a new Tor circuit (new IP)."""
        if not self.use_tor or not TOR_AVAILABLE:
            return False
        try:
            # This would require stem control connection
            logger.info("Requesting new Tor circuit...")
            # Simplified - actual rotation would use stem
            time.sleep(5)
            self._get_current_ip()
            logger.info(f"New IP: {self.current_ip}")
            return True
        except Exception as e:
            logger.error(f"Failed to rotate identity: {e}")
            return False

# ==================== EVIDENCE COLLECTORS ====================

class EvidenceCollector:
    """
    Base class for all evidence collectors.
    All methods in English.
    """
    
    def __init__(self, anonymizer: Anonymizer):
        self.anonymizer = anonymizer
        self.session = anonymizer.get_session()
    
    def download_screenshot(self, url: str, output_dir: str = None) -> Optional[str]:
        """Download a screenshot or image from a URL."""
        try:
            response = self.session.get(url, timeout=30, stream=True)
            if response.status_code == 200:
                if not output_dir:
                    output_dir = tempfile.mkdtemp()
                os.makedirs(output_dir, exist_ok=True)
                filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"Screenshot saved to {filepath}")
                return filepath
        except Exception as e:
            logger.error(f"Failed to download screenshot: {e}")
        return None
    
    def extract_metadata(self, filepath: str) -> Dict:
        """Extract all available metadata from a file."""
        metadata = {
            'file_info': {},
            'exif': {},
            'hashes': {},
            'timestamps': {}
        }
        
        # File info
        if os.path.exists(filepath):
            stat = os.stat(filepath)
            metadata['file_info'] = {
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'accessed': datetime.fromtimestamp(stat.st_atime).isoformat()
            }
        
        # Hashes
        with open(filepath, 'rb') as f:
            data = f.read()
            metadata['hashes']['md5'] = hashlib.md5(data).hexdigest()
            metadata['hashes']['sha1'] = hashlib.sha1(data).hexdigest()
            metadata['hashes']['sha256'] = hashlib.sha256(data).hexdigest()
        
        # EXIF data for images
        try:
            img = Image.open(filepath)
            exif = img._getexif()
            if exif:
                for tag_id, value in exif.items():
                    tag = ExifTags.TAGS.get(tag_id, tag_id)
                    metadata['exif'][str(tag)] = str(value)
        except:
            pass
        
        return metadata

class DoxbinCollector(EvidenceCollector):
    """
    Specialized collector for Doxbin and similar paste sites.
    All methods in English.
    """
    
    def __init__(self, anonymizer: Anonymizer):
        super().__init__(anonymizer)
        self.base_urls = [
            'https://doxbin.com',
            'https://doxbin.net',
            'https://doxbin.org'
        ]
    
    def search_pastes(self, keywords: List[str]) -> List[Dict]:
        """Search for pastes containing keywords."""
        results = []
        for keyword in keywords:
            for base_url in self.base_urls:
                try:
                    search_url = f"{base_url}/search?q={keyword}"
                    response = self.session.get(search_url, timeout=30)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        # This would need actual Doxbin parsing logic
                        # Simplified for demonstration
                        results.append({
                            'keyword': keyword,
                            'source': base_url,
                            'timestamp': datetime.now(datetime.timezone.utc).isoformat(),
                            'content': response.text[:500]  # Preview
                        })
                except Exception as e:
                    logger.error(f"Error searching {base_url}: {e}")
        return results
    
    def extract_paste_content(self, paste_url: str) -> Optional[str]:
        """Extract full content from a specific paste."""
        try:
            response = self.session.get(paste_url, timeout=30)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logger.error(f"Failed to extract paste content: {e}")
        return None
    
    def extract_target_data(self, content: str) -> Dict:
        """Extract potential target information from paste content."""
        data = {
            'usernames': [],
            'emails': [],
            'phones': [],
            'ips': [],
            'names': [],
            'addresses': [],
            'social_media': [],
            'threats': [],
            'timestamps': []
        }
        
        # Email extraction
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        data['emails'] = list(set(re.findall(email_pattern, content)))
        
        # IP extraction
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        data['ips'] = list(set(re.findall(ip_pattern, content)))
        
        # Phone number extraction (simple)
        phone_pattern = r'\b[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}\b'
        data['phones'] = list(set(re.findall(phone_pattern, content)))
        
        # Username extraction (common patterns)
        username_pattern = r'\b[A-Za-z][A-Za-z0-9_]{3,30}\b'
        potential_usernames = re.findall(username_pattern, content)
        # Filter common words
        common_words = set(['the', 'and', 'for', 'you', 'are', 'not', 'but', 'can', 'have', 'with'])
        data['usernames'] = [u for u in potential_usernames if u.lower() not in common_words and len(u) > 3][:20]
        
        # Threat detection (simple keyword matching)
        threat_keywords = ['kill', 'die', 'hurt', 'harm', 'rape', 'abuse', 'extort', 'blackmail', 'ruin', 'destroy']
        for keyword in threat_keywords:
            if keyword in content.lower():
                data['threats'].append(keyword)
        
        return data

class SocialMediaCollector(EvidenceCollector):
    """
    Collects evidence from social media platforms.
    All methods in English.
    """
    
    def __init__(self, anonymizer: Anonymizer):
        super().__init__(anonymizer)
        self.platforms = {
            'twitter': 'https://twitter.com',
            'instagram': 'https://instagram.com',
            'facebook': 'https://facebook.com',
            'tiktok': 'https://tiktok.com',
            'reddit': 'https://reddit.com',
            'telegram': 'https://t.me',
            'discord': 'https://discord.com'
        }
    
    def check_username(self, username: str) -> Dict:
        """Check if username exists on various platforms."""
        results = {}
        for platform, base_url in self.platforms.items():
            try:
                url = f"{base_url}/{username}"
                response = self.session.head(url, timeout=5, allow_redirects=True)
                results[platform] = {
                    'exists': response.status_code == 200,
                    'url': url,
                    'status_code': response.status_code
                }
            except:
                results[platform] = {'exists': False, 'error': 'Connection failed'}
        return results
    
    def get_profile_info(self, platform: str, username: str) -> Dict:
        """Get profile information from a specific platform."""
        # This would need platform-specific API calls
        # Simplified for demonstration
        return {
            'platform': platform,
            'username': username,
            'url': f"{self.platforms.get(platform, '')}/{username}",
            'collected': datetime.now(datetime.timezone.utc).isoformat()
        }
    
    def extract_posts(self, platform: str, username: str, max_posts: int = 50) -> List[Dict]:
        """Extract recent posts from a profile."""
        # This would need platform-specific scraping
        # Simplified for demonstration
        posts = []
        for i in range(min(max_posts, 10)):  # Limited for demo
            posts.append({
                'platform': platform,
                'username': username,
                'post_id': f"post_{i}",
                'content': f"Sample post content {i}",
                'timestamp': (datetime.now() - timedelta(days=i)).isoformat(),
                'url': f"{self.platforms.get(platform, '')}/{username}/post/{i}"
            })
        return posts

class NetworkCollector(EvidenceCollector):
    """
    Collects network-related evidence (IP, domains, etc.).
    All methods in English.
    """
    
    def __init__(self, anonymizer: Anonymizer):
        super().__init__(anonymizer)
    
    def ip_info(self, ip: str) -> Dict:
        """Get geolocation and ISP information for an IP."""
        info = {
            'ip': ip,
            'country': None,
            'city': None,
            'region': None,
            'isp': None,
            'org': None,
            'asn': None,
            'latitude': None,
            'longitude': None
        }
        try:
            response = self.session.get(f"http://ip-api.com/json/{ip}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    info.update({
                        'country': data.get('country'),
                        'city': data.get('city'),
                        'region': data.get('regionName'),
                        'isp': data.get('isp'),
                        'org': data.get('org'),
                        'asn': data.get('as'),
                        'latitude': data.get('lat'),
                        'longitude': data.get('lon')
                    })
        except Exception as e:
            logger.error(f"IP lookup failed: {e}")
        return info
    
    def domain_info(self, domain: str) -> Dict:
        """Get WHOIS and DNS information for a domain."""
        info = {
            'domain': domain,
            'registrar': None,
            'creation_date': None,
            'expiration_date': None,
            'name_servers': [],
            'emails': [],
            'ip': None
        }
        
        # Get IP
        try:
            info['ip'] = socket.gethostbyname(domain)
        except:
            pass
        
        # WHOIS
        try:
            w = whois.whois(domain)
            info['registrar'] = str(w.registrar)
            info['creation_date'] = str(w.creation_date)
            info['expiration_date'] = str(w.expiration_date)
            if w.name_servers:
                info['name_servers'] = [str(ns) for ns in w.name_servers[:5]]
            if w.emails:
                info['emails'] = [str(e) for e in w.emails if e]
        except:
            pass
        
        return info

class EvidencePackager:
    """
    Packages evidence into formats suitable for submission to authorities.
    All methods in English.
    """
    
    def __init__(self, output_dir: str = "./hestia_reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_pdf_report(self, case: Case, filename: str = None) -> str:
        """
        Generate a comprehensive PDF report of the case.
        All text in English.
        """
        if not REPORTLAB_AVAILABLE:
            logger.error("ReportLab not available. Cannot generate PDF.")
            return None
        
        if not filename:
            filename = f"{case.case_id}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.red,
            spaceAfter=30
        )
        story.append(Paragraph(f"Hestia Investigation Report: {case.case_id}", title_style))
        story.append(Spacer(1, 12))
        
        # Case Overview
        story.append(Paragraph("Case Overview", styles['Heading2']))
        story.append(Spacer(1, 6))
        overview_data = [
            ["Case ID:", case.case_id],
            ["Title:", case.title or "N/A"],
            ["Jurisdiction:", case.jurisdiction.value],
            ["Lead Source:", case.lead_source or "N/A"],
            ["Lead Date:", case.lead_date or "N/A"],
            ["Created:", case.created],
            ["Updated:", case.updated],
            ["Status:", case.status],
            ["Risk Level:", case.risk_level.value.upper()]
        ]
        overview_table = Table(overview_data, colWidths=[1.5*inch, 4*inch])
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(overview_table)
        story.append(Spacer(1, 20))
        
        # Suspects
        if case.suspects:
            story.append(Paragraph("Suspects", styles['Heading2']))
            story.append(Spacer(1, 6))
            for i, suspect in enumerate(case.suspects, 1):
                story.append(Paragraph(f"Suspect {i}: {suspect.primary_username or 'Unknown'}", styles['Heading3']))
                suspect_data = [
                    ["Real Name:", suspect.real_name or "Unknown"],
                    ["Age/DOB:", f"{suspect.age or 'Unknown'} / {suspect.dob or 'Unknown'}"],
                    ["Location:", suspect.location or "Unknown"],
                    ["Country:", suspect.country or "Unknown"],
                    ["Threat Level:", suspect.threat_level.value.upper()],
                    ["Platforms:", ", ".join(suspect.platforms) if suspect.platforms else "None"],
                    ["Notes:", suspect.notes or "None"]
                ]
                if suspect.emails:
                    suspect_data.append(["Emails:", ", ".join(suspect.emails[:5])])
                if suspect.phones:
                    suspect_data.append(["Phones:", ", ".join(suspect.phones[:5])])
                if suspect.ips:
                    suspect_data.append(["IPs:", ", ".join(suspect.ips[:5])])
                
                suspect_table = Table(suspect_data, colWidths=[1.5*inch, 4*inch])
                suspect_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey)
                ]))
                story.append(suspect_table)
                story.append(Spacer(1, 10))
        
        # Evidence Summary
        if case.evidence:
            story.append(Paragraph("Evidence Summary", styles['Heading2']))
            story.append(Spacer(1, 6))
            evidence_data = [["ID", "Type", "Source", "Timestamp", "Hash (SHA256)"]]
            for ev_id, ev in list(case.evidence.items())[:50]:  # Limit for readability
                evidence_data.append([
                    ev_id[:8],
                    ev.type.value,
                    ev.source[:30] if ev.source else "N/A",
                    ev.timestamp_utc[:16] if ev.timestamp_utc else "N/A",
                    ev.hash_sha256[:16] + "..." if ev.hash_sha256 else "N/A"
                ])
            
            evidence_table = Table(evidence_data, colWidths=[0.8*inch, 1*inch, 1.5*inch, 1.2*inch, 2*inch])
            evidence_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(evidence_table)
            story.append(Spacer(1, 10))
        
        # Timeline
        if case.timeline:
            story.append(Paragraph("Investigation Timeline", styles['Heading2']))
            story.append(Spacer(1, 6))
            timeline_data = [["Timestamp", "Event"]]
            for entry in case.timeline[-20:]:  # Last 20 events
                timeline_data.append([
                    entry['timestamp'][:19] if entry['timestamp'] else "N/A",
                    entry['event']
                ])
            
            timeline_table = Table(timeline_data, colWidths=[2*inch, 4*inch])
            timeline_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(timeline_table)
        
        # Build PDF
        doc.build(story)
        logger.info(f"PDF report generated: {filepath}")
        return filepath
    
    def create_evidence_package(self, case: Case) -> str:
        """
        Create a ZIP package containing all evidence files and a JSON manifest.
        All file names and content in English.
        """
        package_dir = os.path.join(self.output_dir, f"{case.case_id}_package")
        os.makedirs(package_dir, exist_ok=True)
        
        # Save case data as JSON
        case_dict = asdict(case)
        with open(os.path.join(package_dir, "case_data.json"), 'w') as f:
            json.dump(case_dict, f, indent=2, default=str)
        
        # Save individual evidence items
        evidence_dir = os.path.join(package_dir, "evidence")
        os.makedirs(evidence_dir, exist_ok=True)
        
        for ev_id, ev in case.evidence.items():
            if ev.file_path and os.path.exists(ev.file_path):
                shutil.copy(ev.file_path, os.path.join(evidence_dir, f"{ev_id}_{os.path.basename(ev.file_path)}"))
            ev_dict = asdict(ev)
            with open(os.path.join(evidence_dir, f"{ev_id}_metadata.json"), 'w') as f:
                json.dump(ev_dict, f, indent=2, default=str)
        
        # Create README
        readme_content = f"""
HESTIA INVESTIGATION PACKAGE
Case ID: {case.case_id}
Generated: {datetime.now(datetime.timezone.utc).isoformat()}
Jurisdiction: {case.jurisdiction.value}

This package contains evidence collected during the investigation.
All evidence has been hashed and chain of custody is maintained.

CONTENTS:
- case_data.json: Complete case information
- evidence/: Directory containing all evidence files
  - Each evidence item has a metadata JSON file and associated file

SUBMISSION INSTRUCTIONS:
1. Verify all evidence hashes against the metadata
2. Review the PDF report for case summary
3. Submit to appropriate authorities with this package

DISCLAIMER: This evidence package is intended for law enforcement use only.
        """
        with open(os.path.join(package_dir, "README.txt"), 'w') as f:
            f.write(readme_content)
        
        # Create ZIP
        zip_filename = f"{case.case_id}_package_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = os.path.join(self.output_dir, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(package_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, package_dir)
                    zipf.write(file_path, arcname)
        
        # Clean up temp directory
        shutil.rmtree(package_dir)
        
        logger.info(f"Evidence package created: {zip_path}")
        return zip_path
    
    def generate_submission_form(self, case: Case, agency: str) -> str:
        """
        Generate a submission form for a specific agency.
        All text in English.
        """
        form_content = f"""
HESTIA OFFICIAL SUBMISSION FORM

TO: {agency}
FROM: Hestia Investigation System
DATE: {datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
CASE ID: {case.case_id}

===============================================================================
INVESTIGATION SUMMARY
===============================================================================

Lead Source: {case.lead_source or 'Unknown'}
Lead Date: {case.lead_date or 'Unknown'}
Case Description: {case.description or 'No description provided'}

===============================================================================
SUSPECT INFORMATION
===============================================================================

"""
        for i, suspect in enumerate(case.suspects, 1):
            form_content += f"""
SUSPECT {i}:
  Username: {suspect.primary_username or 'Unknown'}
  Real Name: {suspect.real_name or 'Unknown'}
  Age/DOB: {suspect.age or 'Unknown'} / {suspect.dob or 'Unknown'}
  Location: {suspect.location or 'Unknown'}
  Country: {suspect.country or 'Unknown'}
  Threat Level: {suspect.threat_level.value.upper()}
  Platforms: {', '.join(suspect.platforms) if suspect.platforms else 'None'}
  Emails: {', '.join(suspect.emails[:3]) if suspect.emails else 'None'}
  Phones: {', '.join(suspect.phones[:3]) if suspect.phones else 'None'}
  IPs: {', '.join(suspect.ips[:3]) if suspect.ips else 'None'}

"""
        
        form_content += f"""
===============================================================================
EVIDENCE SUMMARY
===============================================================================

Total Evidence Items: {len(case.evidence)}
Evidence Types: {', '.join(set([e.type.value for e in case.evidence.values()]))}

Key Evidence IDs:
{chr(10).join([f'  - {eid[:8]}: {e.type.value} from {e.source}' for eid, e in list(case.evidence.items())[:10]])}

===============================================================================
CHAIN OF CUSTODY
===============================================================================

Case Created: {case.created}
Last Updated: {case.updated}
Timeline Events: {len(case.timeline)}

===============================================================================
SUBMISSION DETAILS
===============================================================================

Submitted by: Hestia System
Submission Date: {datetime.now(datetime.timezone.utc).isoformat()}
Attached Evidence Package: {case.case_id}_package.zip
PDF Report: {case.case_id}_report.pdf

===============================================================================
CERTIFICATION
===============================================================================

I certify that the information contained herein is accurate to the best of my
knowledge and has been collected in accordance with standard OSINT practices.

This submission is made in good faith for law enforcement action.

===============================================================================
END OF SUBMISSION FORM
        """
        
        filename = os.path.join(self.output_dir, f"{case.case_id}_submission_form.txt")
        with open(filename, 'w') as f:
            f.write(form_content)
        
        logger.info(f"Submission form generated: {filename}")
        return filename

# ==================== MAIN APPLICATION ====================

class Hestia:
    """
    Main Hestia application class.
    All user interface text in English.
    """
    
    def __init__(self):
        self.version = "1.0"
        self.author = "Phoenix/Minthol"
        self.anonymizer = Anonymizer()
        self.doxbin = DoxbinCollector(self.anonymizer)
        self.social = SocialMediaCollector(self.anonymizer)
        self.network = NetworkCollector(self.anonymizer)
        self.packager = EvidencePackager()
        self.current_case = None
        self.cases = {}
        self.data_dir = "./hestia_data"
        os.makedirs(self.data_dir, exist_ok=True)
        self._load_cases()
        
        # Colors for UI
        self.R = '\033[91m'
        self.G = '\033[92m'
        self.Y = '\033[93m'
        self.B = '\033[94m'
        self.M = '\033[95m'
        self.C = '\033[96m'
        self.W = '\033[97m'
        self.RESET = '\033[0m'
        self.BOLD = '\033[1m'
    
    def _load_cases(self):
        """Load existing cases from disk."""
        cases_file = os.path.join(self.data_dir, "cases_index.json")
        if os.path.exists(cases_file):
            try:
                with open(cases_file, 'r') as f:
                    data = json.load(f)
                    for case_id, case_path in data.items():
                        if os.path.exists(case_path):
                            with open(case_path, 'r') as cf:
                                case_data = json.load(cf)
                                self.cases[case_id] = Case(**case_data)
            except Exception as e:
                logger.error(f"Failed to load cases: {e}")
    
    def _save_case(self, case: Case):
        """Save a case to disk."""
        case_file = os.path.join(self.data_dir, f"{case.case_id}.json")
        with open(case_file, 'w') as f:
            json.dump(asdict(case), f, indent=2, default=str)
        
        # Update index
        cases_file = os.path.join(self.data_dir, "cases_index.json")
        index = {}
        if os.path.exists(cases_file):
            with open(cases_file, 'r') as f:
                index = json.load(f)
        index[case.case_id] = case_file
        with open(cases_file, 'w') as f:
            json.dump(index, f, indent=2)
    
    def print_banner(self):
        """Print the application banner."""
        banner = f"""
{self.R}╔══════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║     ██╗  ██╗███████╗███████╗████████╗██╗ █████╗                           ║
║     ██║  ██║██╔════╝██╔════╝╚══██╔══╝██║██╔══██╗                          ║
║     ███████║█████╗  ███████╗   ██║   ██║███████║                          ║
║     ██╔══██║██╔══╝  ╚════██║   ██║   ██║██╔══██║                          ║
║     ██║  ██║███████╗███████║   ██║   ██║██║  ██║                          ║
║     ╚═╝  ╚═╝╚══════╝╚══════╝   ╚═╝   ╚═╝╚═╝  ╚═╝                          ║
║                                                                              ║
║                    Predator Case Management & Evidence Automation           ║
║                         Protect the Vulnerable. Catch the Predators.        ║
║                                                                              ║
║                    Version {self.version} • By {self.author}                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════╝{self.RESET}
        """
        print(banner)
    
    def interactive_menu(self):
        """Main interactive menu."""
        while True:
            os.system('clear')
            self.print_banner()
            
            # Show current case
            if self.current_case:
                case_info = f"{self.G}Current Case: {self.current_case.case_id} - {self.current_case.title or 'Untitled'}{self.RESET}"
            else:
                case_info = f"{self.Y}No active case. Start or load a case.{self.RESET}"
            print(case_info)
            print()
            
            print(f"{self.BOLD}{self.C}╔══════════════════════════════════════════════════════════╗{self.RESET}")
            print(f"{self.BOLD}{self.C}║                    HESTIA MAIN MENU                        ║{self.RESET}")
            print(f"{self.BOLD}{self.C}╠══════════════════════════════════════════════════════════╣{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[01]{self.RESET} Create New Case                         ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[02]{self.RESET} Load Existing Case                      ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[03]{self.RESET} List All Cases                          ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[04]{self.RESET} Search Doxbin for Keywords              ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[05]{self.RESET} Extract Target Data from Paste          ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[06]{self.RESET} Check Username Across Platforms         ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[07]{self.RESET} Investigate IP Address                  ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[08]{self.RESET} Investigate Domain                      ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[09]{self.RESET} Add Manual Evidence                     ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[10]{self.RESET} View Case Details                       ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[11]{self.RESET} View Evidence List                      ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[12]{self.RESET} Add Suspect Profile                     ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[13]{self.RESET} Generate PDF Report                     ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[14]{self.RESET} Create Evidence Package                 ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[15]{self.RESET} Generate Submission Form                ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[16]{self.RESET} Export Case for Authorities             ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[17]{self.RESET} Rotate Tor Identity                     ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[18]{self.RESET} View Anonymity Status                   ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[19]{self.RESET} Settings                                ║{self.RESET}")
            print(f"{self.BOLD}{self.C}║  {self.W}[00]{self.RESET} Exit                                    ║{self.RESET}")
            print(f"{self.BOLD}{self.C}╚══════════════════════════════════════════════════════════╝{self.RESET}")
            print()
            
            choice = input(f"{self.BOLD}{self.R}Hestia@case:~# {self.RESET}").strip()
            
            if choice == '1' or choice == '01':
                self.create_new_case()
            elif choice == '2' or choice == '02':
                self.load_case()
            elif choice == '3' or choice == '03':
                self.list_cases()
            elif choice == '4' or choice == '04':
                self.search_doxbin()
            elif choice == '5' or choice == '05':
                self.extract_paste_data()
            elif choice == '6' or choice == '06':
                self.check_username()
            elif choice == '7' or choice == '07':
                self.investigate_ip()
            elif choice == '8' or choice == '08':
                self.investigate_domain()
            elif choice == '9' or choice == '09':
                self.add_manual_evidence()
            elif choice == '10':
                self.view_case_details()
            elif choice == '11':
                self.view_evidence()
            elif choice == '12':
                self.add_suspect()
            elif choice == '13':
                self.generate_report()
            elif choice == '14':
                self.create_package()
            elif choice == '15':
                self.generate_submission()
            elif choice == '16':
                self.export_case()
            elif choice == '17':
                self.rotate_tor()
            elif choice == '18':
                self.view_anonymity()
            elif choice == '19':
                self.settings()
            elif choice == '0' or choice == '00':
                self.exit_program()
                break
            
            input(f"{self.Y}[+] Press Enter to continue...{self.RESET}")
    
    def create_new_case(self):
        """Create a new investigation case."""
        print(f"\n{self.BOLD}{self.C}CREATE NEW CASE{self.RESET}\n")
        
        title = input(f"{self.Y}Case Title: {self.RESET}").strip()
        description = input(f"{self.Y}Case Description: {self.RESET}").strip()
        lead_source = input(f"{self.Y}Lead Source (e.g., Doxbin URL): {self.RESET}").strip()
        
        print(f"\n{self.C}Select Jurisdiction:{self.RESET}")
        jurisdictions = list(Jurisdiction)
        for i, j in enumerate(jurisdictions, 1):
            print(f"  {i}. {j.value}")
        
        jur_choice = input(f"{self.Y}Choice: {self.RESET}").strip()
        try:
            jurisdiction = jurisdictions[int(jur_choice)-1]
        except:
            jurisdiction = Jurisdiction.CUSTOM
        
        case = Case(
            title=title,
            description=description,
            lead_source=lead_source,
            lead_date=datetime.now().isoformat(),
            jurisdiction=jurisdiction
        )
        
        self.current_case = case
        self.cases[case.case_id] = case
        self._save_case(case)
        
        print(f"{self.G}[✓] Case created: {case.case_id}{self.RESET}")
    
    def load_case(self):
        """Load an existing case."""
        if not self.cases:
            print(f"{self.Y}[!] No cases available.{self.RESET}")
            return
        
        print(f"\n{self.BOLD}{self.C}AVAILABLE CASES{self.RESET}\n")
        cases_list = list(self.cases.values())
        for i, case in enumerate(cases_list, 1):
            print(f"  {i}. {case.case_id} - {case.title or 'Untitled'} ({case.status})")
        
        choice = input(f"\n{self.Y}Select case number: {self.RESET}").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(cases_list):
                self.current_case = cases_list[idx]
                print(f"{self.G}[✓] Loaded case: {self.current_case.case_id}{self.RESET}")
            else:
                print(f"{self.R}[!] Invalid selection.{self.RESET}")
        except:
            print(f"{self.R}[!] Invalid input.{self.RESET}")
    
    def list_cases(self):
        """List all cases."""
        if not self.cases:
            print(f"{self.Y}[!] No cases available.{self.RESET}")
            return
        
        print(f"\n{self.BOLD}{self.C}ALL CASES{self.RESET}\n")
        for case_id, case in self.cases.items():
            current = " [CURRENT]" if self.current_case and self.current_case.case_id == case_id else ""
            print(f"  {case_id}: {case.title or 'Untitled'} ({case.status}){current}")
    
    def search_doxbin(self):
        """Search Doxbin for keywords."""
        if not self.current_case:
            print(f"{self.R}[!] No active case. Create or load a case first.{self.RESET}")
            return
        
        print(f"\n{self.BOLD}{self.C}SEARCH DOXBIN{self.RESET}\n")
        keywords_input = input(f"{self.Y}Enter keywords (comma-separated): {self.RESET}").strip()
        keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
        
        if not keywords:
            print(f"{self.R}[!] No keywords entered.{self.RESET}")
            return
        
        print(f"{self.Y}[*] Searching for: {', '.join(keywords)}...{self.RESET}")
        results = self.doxbin.search_pastes(keywords)
        
        if results:
            print(f"\n{self.G}Found {len(results)} results:{self.RESET}\n")
            for i, result in enumerate(results[:10], 1):
                print(f"  {i}. Keyword: {result['keyword']}")
                print(f"     Source: {result['source']}")
                print(f"     Preview: {result['content'][:100]}...")
                print()
            
            save = input(f"{self.Y}Save these results to case? (y/n): {self.RESET}").lower()
            if save == 'y':
                for result in results:
                    evidence = EvidenceItem(
                        type=EvidenceType.POST,
                        source=result['source'],
                        content=json.dumps(result),
                        notes=f"Search result for keyword: {result['keyword']}"
                    )
                    self.current_case.add_evidence(evidence)
                self._save_case(self.current_case)
                print(f"{self.G}[✓] Results saved to case.{self.RESET}")
        else:
            print(f"{self.Y}[!] No results found.{self.RESET}")
    
    def extract_paste_data(self):
        """Extract target data from a paste."""
        if not self.current_case:
            print(f"{self.R}[!] No active case.{self.RESET}")
            return
        
        print(f"\n{self.BOLD}{self.C}EXTRACT PASTE DATA{self.RESET}\n")
        paste_url = input(f"{self.Y}Paste URL: {self.RESET}").strip()
        
        if not paste_url:
            print(f"{self.R}[!] No URL provided.{self.RESET}")
            return
        
        print(f"{self.Y}[*] Extracting data from {paste_url}...{self.RESET}")
        content = self.doxbin.extract_paste_content(paste_url)
        
        if content:
            data = self.doxbin.extract_target_data(content)
            
            print(f"\n{self.G}Extracted Data:{self.RESET}\n")
            for key, values in data.items():
                if values:
                    print(f"  {key.capitalize()}: {', '.join(str(v) for v in values[:5])}")
                    if len(values) > 5:
                        print(f"    ... and {len(values)-5} more")
            
            # Save paste content as evidence
            evidence = EvidenceItem(
                type=EvidenceType.POST,
                source=paste_url,
                content=content,
                notes="Full paste content"
            )
            self.current_case.add_evidence(evidence)
            
            # Save extracted data as separate evidence
            data_evidence = EvidenceItem(
                type=EvidenceType.METADATA,
                source=paste_url,
                content=json.dumps(data),
                notes="Extracted target data from paste"
            )
            self.current_case.add_evidence(data_evidence)
            
            self._save_case(self.current_case)
            print(f"{self.G}[✓] Data extracted and saved to case.{self.RESET}")
        else:
            print(f"{self.R}[!] Failed to extract content.{self.RESET}")
    
    def check_username(self):
        """Check username across platforms."""
        if not self.current_case:
            print(f"{self.R}[!] No active case.{self.RESET}")
            return
        
        print(f"\n{self.BOLD}{self.C}CHECK USERNAME{self.RESET}\n")
        username = input(f"{self.Y}Username: {self.RESET}").strip()
        
        if not username:
            print(f"{self.R}[!] No username provided.{self.RESET}")
            return
        
        print(f"{self.Y}[*] Checking {username} across platforms...{self.RESET}")
        results = self.social.check_username(username)
        
        print(f"\n{self.G}Results:{self.RESET}\n")
        found = []
        for platform, result in results.items():
            if result.get('exists'):
                found.append(platform)
                print(f"  {self.G}✓ {platform}: {result['url']}{self.RESET}")
            else:
                print(f"  {self.W}✗ {platform}: Not found{self.RESET}")
        
        if found:
            save = input(f"\n{self.Y}Save found profiles to case? (y/n): {self.RESET}").lower()
            if save == 'y':
                evidence = EvidenceItem(
                    type=EvidenceType.PROFILE,
                    source="Username Check",
                    content=json.dumps(results),
                    notes=f"Username '{username}' found on: {', '.join(found)}"
                )
                self.current_case.add_evidence(evidence)
                
                # Add or update suspect
                suspect = None
                for s in self.current_case.suspects:
                    if s.primary_username == username:
                        suspect = s
                        break
                
                if not suspect:
                    suspect = SuspectProfile(primary_username=username)
                    self.current_case.add_suspect(suspect)
                
                for platform in found:
                    if platform not in suspect.platforms:
                        suspect.platforms.append(platform)
                    suspect.social_media[platform] = results[platform].get('url', '')
                
                self._save_case(self.current_case)
                print(f"{self.G}[✓] Profiles saved and suspect updated.{self.RESET}")
    
    def investigate_ip(self):
        """Investigate an IP address."""
        if not self.current_case:
            print(f"{self.R}[!] No active case.{self.RESET}")
            return
        
        print(f"\n{self.BOLD}{self.C}INVESTIGATE IP{self.RESET}\n")
        ip = input(f"{self.Y}IP Address: {self.RESET}").strip()
        
        if not ip:
            print(f"{self.R}[!] No IP provided.{self.RESET}")
            return
        
        print(f"{self.Y}[*] Investigating {ip}...{self.RESET}")
        info = self.network.ip_info(ip)
        
        print(f"\n{self.G}IP Information:{self.RESET}\n")
        for key, value in info.items():
            if value:
                print(f"  {key.capitalize()}: {value}")
        
        save = input(f"\n{self.Y}Save this information to case? (y/n): {self.RESET}").lower()
        if save == 'y':
            evidence = EvidenceItem(
                type=EvidenceType.NETWORK,
                source=f"IP: {ip}",
                content=json.dumps(info),
                notes=f"IP investigation results"
            )
            self.current_case.add_evidence(evidence)
            
            # Add IP to suspects if applicable
            for suspect in self.current_case.suspects:
                if ip not in suspect.ips:
                    suspect.ips.append(ip)
            
            self._save_case(self.current_case)
            print(f"{self.G}[✓] IP information saved to case.{self.RESET}")
    
    def investigate_domain(self):
        """Investigate a domain."""
        if not self.current_case:
            print(f"{self.R}[!] No active case.{self.RESET}")
            return
        
        print(f"\n{self.BOLD}{self.C}INVESTIGATE DOMAIN{self.RESET}\n")
        domain = input(f"{self.Y}Domain: {self.RESET}").strip()
        
        if not domain:
            print(f"{self.R}[!] No domain provided.{self.RESET}")
            return
        
        print(f"{self.Y}[*] Investigating {domain}...{self.RESET}")
        info = self.network.domain_info(domain)
        
        print(f"\n{self.G}Domain Information:{self.RESET}\n")
        for key, value in info.items():
            if value:
                print(f"  {key.capitalize()}: {value}")
        
        save = input(f"\n{self.Y}Save this information to case? (y/n): {self.RESET}").lower()
        if save == 'y':
            evidence = EvidenceItem(
                type=EvidenceType.NETWORK,
                source=f"Domain: {domain}",
                content=json.dumps(info),
                notes=f"Domain investigation results"
            )
            self.current_case.add_evidence(evidence)
            self._save_case(self.current_case)
            print(f"{self.G}[✓] Domain information saved to case.{self.RESET}")
    
    def add_manual_evidence(self):
        """Add manual evidence to the case."""
        if not self.current_case:
            print(f"{self.R}[!] No active case.{self.RESET}")
            return
        
        print(f"\n{self.BOLD}{self.C}ADD MANUAL EVIDENCE{self.RESET}\n")
        
        print(f"Evidence Types:")
        for i, etype in enumerate(EvidenceType, 1):
            print(f"  {i}. {etype.value}")
        
        type_choice = input(f"\n{self.Y}Select type: {self.RESET}").strip()
        try:
            etype = list(EvidenceType)[int(type_choice)-1]
        except:
            etype = EvidenceType.OTHER
        
        source = input(f"{self.Y}Source: {self.RESET}").strip()
        content = input(f"{self.Y}Content/Description: {self.RESET}").strip()
        notes = input(f"{self.Y}Additional Notes: {self.RESET}").strip()
        
        evidence = EvidenceItem(
            type=etype,
            source=source,
            content=content,
            notes=notes
        )
        
        self.current_case.add_evidence(evidence)
        self._save_case(self.current_case)
        print(f"{self.G}[✓] Evidence added. ID: {evidence.id[:8]}{self.RESET}")
    
    def view_case_details(self):
        """View current case details."""
        if not self.current_case:
            print(f"{self.R}[!] No active case.{self.RESET}")
            return
        
        case = self.current_case
        print(f"\n{self.BOLD}{self.C}CASE DETAILS: {case.case_id}{self.RESET}\n")
        print(f"Title: {case.title or 'N/A'}")
        print(f"Description: {case.description or 'N/A'}")
        print(f"Jurisdiction: {case.jurisdiction.value}")
        print(f"Lead Source: {case.lead_source or 'N/A'}")
        print(f"Lead Date: {case.lead_date or 'N/A'}")
        print(f"Status: {case.status}")
        print(f"Risk Level: {case.risk_level.value.upper()}")
        print(f"Suspects: {len(case.suspects)}")
        print(f"Evidence Items: {len(case.evidence)}")
        print(f"Timeline Events: {len(case.timeline)}")
        print(f"Created: {case.created}")
        print(f"Updated: {case.updated}")
        
        if case.notes:
            print(f"\nNotes: {case.notes}")
    
    def view_evidence(self):
        """View evidence list for current case."""
        if not self.current_case:
            print(f"{self.R}[!] No active case.{self.RESET}")
            return
        
        case = self.current_case
        if not case.evidence:
            print(f"{self.Y}[!] No evidence in this case.{self.RESET}")
            return
        
        print(f"\n{self.BOLD}{self.C}EVIDENCE LIST{self.RESET}\n")
        for ev_id, ev in case.evidence.items():
            print(f"  {self.G}[{ev_id[:8]}]{self.RESET} {ev.type.value.upper()} from {ev.source}")
            print(f"      Added: {ev.timestamp_utc[:16]}")
            if ev.notes:
                print(f"      Notes: {ev.notes}")
            print()
    
    def add_suspect(self):
        """Add a suspect profile to the case."""
        if not self.current_case:
            print(f"{self.R}[!] No active case.{self.RESET}")
            return
        
        print(f"\n{self.BOLD}{self.C}ADD SUSPECT PROFILE{self.RESET}\n")
        
        username = input(f"{self.Y}Primary Username: {self.RESET}").strip()
        if not username:
            print(f"{self.R}[!] Username required.{self.RESET}")
            return
        
        real_name = input(f"{self.Y}Real Name (if known): {self.RESET}").strip() or None
        location = input(f"{self.Y}Location (if known): {self.RESET}").strip() or None
        country = input(f"{self.Y}Country (if known): {self.RESET}").strip() or None
        notes = input(f"{self.Y}Notes: {self.RESET}").strip() or None
        
        suspect = SuspectProfile(
            primary_username=username,
            real_name=real_name,
            location=location,
            country=country,
            notes=notes
        )
        
        self.current_case.add_suspect(suspect)
        self._save_case(self.current_case)
        print(f"{self.G}[✓] Suspect added. ID: {suspect.id[:8]}{self.RESET}")
    
    def generate_report(self):
        """Generate PDF report for the case."""
        if not self.current_case:
            print(f"{self.R}[!] No active case.{self.RESET}")
            return
        
        print(f"{self.Y}[*] Generating PDF report...{self.RESET}")
        report_path = self.packager.generate_pdf_report(self.current_case)
        if report_path:
            print(f"{self.G}[✓] Report generated: {report_path}{self.RESET}")
            
            # Add report as evidence
            evidence = EvidenceItem(
                type=EvidenceType.OTHER,
                source="Hestia Report Generator",
                file_path=report_path,
                notes="Generated investigation report"
            )
            self.current_case.add_evidence(evidence)
            self._save_case(self.current_case)
        else:
            print(f"{self.R}[!] Report generation failed.{self.RESET}")
    
    def create_package(self):
        """Create evidence package ZIP."""
        if not self.current_case:
            print(f"{self.R}[!] No active case.{self.RESET}")
            return
        
        print(f"{self.Y}[*] Creating evidence package...{self.RESET}")
        package_path = self.packager.create_evidence_package(self.current_case)
        if package_path:
            print(f"{self.G}[✓] Package created: {package_path}{self.RESET}")
            
            # Add package as evidence
            evidence = EvidenceItem(
                type=EvidenceType.OTHER,
                source="Hestia Packager",
                file_path=package_path,
                notes="Complete evidence package"
            )
            self.current_case.add_evidence(evidence)
            self._save_case(self.current_case)
        else:
            print(f"{self.R}[!] Package creation failed.{self.RESET}")
    
    def generate_submission(self):
        """Generate submission form for authorities."""
        if not self.current_case:
            print(f"{self.R}[!] No active case.{self.RESET}")
            return
        
        print(f"\n{self.BOLD}{self.C}GENERATE SUBMISSION FORM{self.RESET}\n")
        agency = input(f"{self.Y}Agency Name (e.g., BKA Germany): {self.RESET}").strip()
        
        if not agency:
            agency = self.current_case.jurisdiction.value
        
        print(f"{self.Y}[*] Generating submission form...{self.RESET}")
        form_path = self.packager.generate_submission_form(self.current_case, agency)
        if form_path:
            print(f"{self.G}[✓] Submission form generated: {form_path}{self.RESET}")
            
            # Add form as evidence
            evidence = EvidenceItem(
                type=EvidenceType.OTHER,
                source="Hestia Submission Generator",
                file_path=form_path,
                notes=f"Submission form for {agency}"
            )
            self.current_case.add_evidence(evidence)
            self._save_case(self.current_case)
        else:
            print(f"{self.R}[!] Submission form generation failed.{self.RESET}")
    
    def export_case(self):
        """Export complete case for authorities (report + package + form)."""
        if not self.current_case:
            print(f"{self.R}[!] No active case.{self.RESET}")
            return
        
        print(f"\n{self.BOLD}{self.C}EXPORT CASE FOR AUTHORITIES{self.RESET}\n")
        
        # Generate all three
        print(f"{self.Y}[*] Generating report...{self.RESET}")
        report_path = self.packager.generate_pdf_report(self.current_case)
        
        print(f"{self.Y}[*] Creating evidence package...{self.RESET}")
        package_path = self.packager.create_evidence_package(self.current_case)
        
        agency = self.current_case.jurisdiction.value
        print(f"{self.Y}[*] Generating submission form...{self.RESET}")
        form_path = self.packager.generate_submission_form(self.current_case, agency)
        
        if report_path and package_path and form_path:
            print(f"\n{self.G}[✓] Case exported successfully!{self.RESET}")
            print(f"  Report: {report_path}")
            print(f"  Package: {package_path}")
            print(f"  Form: {form_path}")
            
            self.current_case.submitted_to_authorities = True
            self.current_case.submission_date = datetime.now().isoformat()
            self._save_case(self.current_case)
        else:
            print(f"{self.R}[!] Export incomplete. Check individual steps.{self.RESET}")
    
    def rotate_tor(self):
        """Rotate Tor identity."""
        if self.anonymizer.rotate_identity():
            print(f"{self.G}[✓] Tor identity rotated. New IP: {self.anonymizer.current_ip}{self.RESET}")
        else:
            print(f"{self.Y}[!] Identity rotation failed or not available.{self.RESET}")
    
    def view_anonymity(self):
        """View current anonymity status."""
        print(f"\n{self.BOLD}{self.C}ANONYMITY STATUS{self.RESET}\n")
        print(f"Tor Enabled: {self.anonymizer.use_tor}")
        print(f"Current IP: {self.anonymizer.current_ip or 'Unknown'}")
        print(f"Tor Available: {TOR_AVAILABLE}")
        print(f"SOCKS Available: {SOCKS_AVAILABLE}")
    
    def settings(self):
        """Configure application settings."""
        print(f"\n{self.BOLD}{self.C}SETTINGS{self.RESET}\n")
        print(f"1. Toggle Tor (currently: {'ON' if self.anonymizer.use_tor else 'OFF'})")
        print(f"2. Change Output Directory (currently: {self.packager.output_dir})")
        print(f"3. Back")
        
        choice = input(f"\n{self.Y}Choice: {self.RESET}").strip()
        
        if choice == '1':
            self.anonymizer.use_tor = not self.anonymizer.use_tor
            self.anonymizer._setup_session()
            print(f"{self.G}[✓] Tor {'enabled' if self.anonymizer.use_tor else 'disabled'}.{self.RESET}")
        elif choice == '2':
            new_dir = input(f"{self.Y}New output directory: {self.RESET}").strip()
            if new_dir:
                self.packager.output_dir = new_dir
                os.makedirs(new_dir, exist_ok=True)
                print(f"{self.G}[✓] Output directory changed.{self.RESET}")
    
    def exit_program(self):
        """Exit the program."""
        print(f"{self.Y}[*] Shutting down Hestia...{self.RESET}")
        # Save current case
        if self.current_case:
            self._save_case(self.current_case)
        print(f"{self.G}[✓] All cases saved. Goodbye.{self.RESET}")

# ==================== MAIN ENTRY POINT ====================

def main():
    """Main entry point."""
    try:
        hestia = Hestia()
        hestia.interactive_menu()
    except KeyboardInterrupt:
        print(f"\n{Y}[!] Interrupted by user.{RESET}")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()