"""
QUEST Video Database Models & Schema Definitions
================================================
Defines structured video entities, taxonomy enums, duration calculators,
tag generators, and validation helpers for the Knowledge Library.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Literal, Dict, Any
import re

LanguageType = Literal["en", "hi"]
LevelType = Literal["Beginner", "Intermediate", "Advanced"]
DurationCategoryType = Literal["Short", "Standard", "Deep Dive"]

# Stage / Module mapping to Level Taxonomy
MODULE_LEVEL_MAP: Dict[str, LevelType] = {
    "module_1": "Beginner",
    "module_2": "Beginner",
    "module_3": "Beginner",
    "module_4": "Intermediate",
    "module_5": "Intermediate",
    "module_6": "Intermediate",
    "module_7": "Advanced",
    "module_8": "Advanced",
    "module_9": "Advanced",
    "module_10": "Advanced",
    "module_tax": "Advanced",
}

# Curated tags catalog mapped by module keywords & concepts
TAG_KEYWORDS_MAP: Dict[str, List[str]] = {
    "module_1": ["Demat Account", "Investing Basics", "Stock Market Fundamentals", "NSE & BSE", "Beginner Investing"],
    "module_2": ["Compounding", "SIP & Mutual Funds", "Index Investing", "Wealth Creation", "Long-term Investing"],
    "module_3": ["Goal Planning", "Asset Allocation", "Emergency Fund", "Financial Freedom", "Retirement Planning"],
    "module_4": ["Investment Strategy", "Value vs Growth", "Portfolio Style", "Market Capitalization", "Dividend Investing"],
    "module_5": ["Portfolio Construction", "Diversification", "Risk Management", "Rebalancing", "Core & Satellite"],
    "module_6": ["Market Volatility", "Hedging & Risk", "Stop Loss Strategy", "Drawdown Management", "Behavioral Finance"],
    "module_7": ["Market News & Catalysts", "Macroeconomics", "RBI Policy & Interest Rates", "Earnings Season", "Sentiment Analysis"],
    "module_8": ["Technical Analysis", "Fundamental Analysis", "P/E & Financial Ratios", "Candlestick Patterns", "Chart Trends"],
    "module_9": ["Market Crashes", "Economic Cycles", "Bear Market Strategy", "Panic Management", "Market History"],
    "module_10": ["Taxation & ITR", "Capital Gains Tax", "Section 80C & Deductions", "Tax Harvesting", "Tax Planning"],
}


def parse_duration_seconds(duration_str: str) -> int:
    """Parses duration strings like '8:45', '11:20', '1:05:30' into total seconds."""
    if not duration_str or not isinstance(duration_str, str):
        return 600  # Default 10 mins
    parts = duration_str.strip().split(":")
    try:
        if len(parts) == 2:
            mins, secs = int(parts[0]), int(parts[1])
            return mins * 60 + secs
        elif len(parts) == 3:
            hours, mins, secs = int(parts[0]), int(parts[1]), int(parts[2])
            return hours * 3600 + mins * 60 + secs
        elif len(parts) == 1 and parts[0].isdigit():
            return int(parts[0])
    except Exception:
        pass
    return 600


def get_duration_category(duration_seconds: int) -> DurationCategoryType:
    """Categorizes duration:
    - Short: < 10 mins (< 600s)
    - Standard: 10–20 mins (600s – 1200s)
    - Deep Dive: > 20 mins (> 1200s)
    """
    if duration_seconds < 600:
        return "Short"
    elif duration_seconds <= 1200:
        return "Standard"
    else:
        return "Deep Dive"


def format_duration(duration_seconds: int) -> str:
    """Formats total seconds into MM:SS or HH:MM:SS."""
    if duration_seconds < 3600:
        mins = duration_seconds // 60
        secs = duration_seconds % 60
        return f"{mins}:{secs:02d}"
    else:
        hours = duration_seconds // 3600
        rem = duration_seconds % 3600
        mins = rem // 60
        secs = rem % 60
        return f"{hours}:{mins:02d}:{secs:02d}"


def get_module_level(module_id: str) -> LevelType:
    """Returns the Level taxonomy for a given module identifier."""
    clean_mod = module_id.lower().strip()
    return MODULE_LEVEL_MAP.get(clean_mod, "Beginner")


def generate_topic_tags(module_id: str, topic_name: str, base_tags: Optional[List[str]] = None) -> List[str]:
    """Generates a clean list of domain tags for a given topic."""
    tags = list(base_tags) if base_tags else []
    mod_tags = TAG_KEYWORDS_MAP.get(module_id.lower().strip(), ["Investing", "Stock Market"])
    
    # Topic specific keywords
    topic_lower = topic_name.lower()
    if "demat" in topic_lower and "Demat Account" not in tags:
        tags.append("Demat Account")
    if "tax" in topic_lower and "Taxation" not in tags:
        tags.append("Taxation")
    if "sip" in topic_lower and "SIP" not in tags:
        tags.append("SIP")
    if "mutual fund" in topic_lower and "Mutual Funds" not in tags:
        tags.append("Mutual Funds")
    if "technical" in topic_lower and "Technical Analysis" not in tags:
        tags.append("Technical Analysis")
    if "fundamental" in topic_lower and "Fundamental Analysis" not in tags:
        tags.append("Fundamental Analysis")
    if "nifty" in topic_lower and "NIFTY 50" not in tags:
        tags.append("NIFTY 50")
    if "risk" in topic_lower and "Risk Management" not in tags:
        tags.append("Risk Management")
    if "balance sheet" in topic_lower and "Financial Statements" not in tags:
        tags.append("Financial Statements")
    if "ratio" in topic_lower and "Financial Ratios" not in tags:
        tags.append("Financial Ratios")
    if "crypto" in topic_lower and "Crypto & Alternate Assets" not in tags:
        tags.append("Crypto & Alternate Assets")
    if "gold" in topic_lower and "Gold & Commodities" not in tags:
        tags.append("Gold & Commodities")

    # Add module tags
    for t in mod_tags:
        if t not in tags:
            tags.append(t)
        
    return tags[:5]


@dataclass
class VideoEntity:
    """Structured Video Entity Model for Knowledge Library."""
    id: str
    title: str
    creator: str
    language: LanguageType
    lang_code: LanguageType
    level: LevelType
    tags: List[str]
    duration: str
    duration_seconds: int
    duration_category: DurationCategoryType
    equivalent_video_id: str
    youtube_id: str
    views: str = "350K"
    published: str = "Recently"
    summary: str = ""
    key_takeaways: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converts entity to clean JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], module_id: str = "module_1", topic_name: str = "", counterpart_id: str = "") -> "VideoEntity":
        """Instantiates and hydrates a VideoEntity from dictionary with automatic validation and fallback defaults."""
        v_id = str(data.get("id", "")).strip()
        raw_lang = str(data.get("language", "")).lower()
        raw_code = str(data.get("lang_code", "")).lower()
        
        # Standardize language enum ('en' | 'hi')
        if raw_lang in ["hi", "hindi", "हिन्दी"] or raw_code == "hi" or v_id.endswith("_hi"):
            lang: LanguageType = "hi"
            lang_code: LanguageType = "hi"
        else:
            lang: LanguageType = "en"
            lang_code: LanguageType = "en"

        # Level ('Beginner' | 'Intermediate' | 'Advanced')
        level = data.get("level") or get_module_level(module_id)
        if level not in ["Beginner", "Intermediate", "Advanced"]:
            level = get_module_level(module_id)

        # Duration & Duration Category ('Short' | 'Standard' | 'Deep Dive')
        raw_dur = str(data.get("duration", "8:45"))
        dur_secs = data.get("duration_seconds")
        if dur_secs is None or not isinstance(dur_secs, int) or dur_secs <= 0:
            dur_secs = parse_duration_seconds(raw_dur)
        
        dur_cat = data.get("duration_category") or get_duration_category(dur_secs)
        if dur_cat not in ["Short", "Standard", "Deep Dive"]:
            dur_cat = get_duration_category(dur_secs)

        # Equivalent counterpart video ID
        eq_id = data.get("equivalent_video_id") or counterpart_id
        if not eq_id:
            if v_id.endswith("_en"):
                eq_id = v_id[:-3] + "_hi"
            elif v_id.endswith("_hi"):
                eq_id = v_id[:-3] + "_en"

        # Tags
        tags = data.get("tags")
        if not tags or not isinstance(tags, list):
            tags = generate_topic_tags(module_id, topic_name or data.get("title", ""))

        return cls(
            id=v_id,
            title=str(data.get("title", "Investing Lesson")),
            creator=str(data.get("creator", "Finance Expert")),
            language=lang,
            lang_code=lang_code,
            level=level,
            tags=tags,
            duration=raw_dur,
            duration_seconds=dur_secs,
            duration_category=dur_cat,
            equivalent_video_id=eq_id,
            youtube_id=str(data.get("youtube_id", "GcZW24SkbHM")),
            views=str(data.get("views", "350K")),
            published=str(data.get("published", "Recently")),
            summary=str(data.get("summary", "")),
            key_takeaways=list(data.get("key_takeaways", []))
        )
