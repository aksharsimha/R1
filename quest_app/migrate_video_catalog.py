"""
QUEST Video Catalog Migration & Seeding Script
==============================================
Backfills and enriches all video entities in quest_app/education_catalog.json with:
- `language`: 'en' | 'hi'
- `level`: 'Beginner' | 'Intermediate' | 'Advanced'
- `tags`: List of domain strings (e.g. ['Demat Account', 'Taxation', ...])
- `duration_category`: 'Short' | 'Standard' | 'Deep Dive'
- `duration_seconds`: Integer runtime in seconds
- `equivalent_video_id`: Bi-directional counterpart foreign key ID
"""

import json
import os
import sys

# Ensure UTF-8 output on Windows terminal
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = os.path.dirname(os.path.abspath(__file__))
_CATALOG_PATH = os.path.join(_HERE, "education_catalog.json")

# Import our video schema & model
from video_models import VideoEntity, get_module_level, get_duration_category, parse_duration_seconds, generate_topic_tags


def run_migration():
    print("=" * 70)
    print("🚀 STARTING VIDEO CATALOG DATABASE MIGRATION & SEEDING")
    print("=" * 70)

    if not os.path.exists(_CATALOG_PATH):
        print(f"❌ Error: Catalog file not found at {_CATALOG_PATH}")
        return False

    with open(_CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    print(f"📁 Loaded Catalog: {len(catalog)} Modules")

    total_topics = 0
    total_videos = 0
    stats = {
        "en": 0,
        "hi": 0,
        "levels": {"Beginner": 0, "Intermediate": 0, "Advanced": 0},
        "duration_categories": {"Short": 0, "Standard": 0, "Deep Dive": 0},
        "linked_pairs": 0,
    }

    all_video_ids = set()

    # Pass 1: Migrate and Hydrate Entities
    for m_idx, mod in enumerate(catalog):
        mod_id = mod.get("module_id", f"module_{m_idx+1}")
        level = get_module_level(mod_id)
        mod["level"] = level
        
        topics = mod.get("topics", [])
        total_topics += len(topics)

        for t_idx, topic_obj in enumerate(topics):
            topic_title = topic_obj.get("topic", f"Topic {t_idx+1}")
            
            en_raw = topic_obj.get("en", {})
            hi_raw = topic_obj.get("hi", {})

            en_id = en_raw.get("id", f"{mod_id}_t{t_idx+1}_en")
            hi_id = hi_raw.get("id", f"{mod_id}_t{t_idx+1}_hi")

            # Convert to structured VideoEntity models
            en_entity = VideoEntity.from_dict(
                en_raw,
                module_id=mod_id,
                topic_name=topic_title,
                counterpart_id=hi_id
            )
            hi_entity = VideoEntity.from_dict(
                hi_raw,
                module_id=mod_id,
                topic_name=topic_title,
                counterpart_id=en_id
            )

            # Ensure bi-directional link
            en_entity.equivalent_video_id = hi_id
            hi_entity.equivalent_video_id = en_id

            # Save back to catalog structure
            topic_obj["en"] = en_entity.to_dict()
            topic_obj["hi"] = hi_entity.to_dict()

            all_video_ids.add(en_entity.id)
            all_video_ids.add(hi_entity.id)

            total_videos += 2
            stats["en"] += 1
            stats["hi"] += 1
            stats["levels"][en_entity.level] += 1
            stats["levels"][hi_entity.level] += 1
            stats["duration_categories"][en_entity.duration_category] += 1
            stats["duration_categories"][hi_entity.duration_category] += 1
            stats["linked_pairs"] += 1

    # Pass 2: Integrity Verification
    broken_links = []
    for mod in catalog:
        for topic in mod.get("topics", []):
            for lang_k in ["en", "hi"]:
                v = topic.get(lang_k, {})
                eq_id = v.get("equivalent_video_id")
                if not eq_id or eq_id not in all_video_ids:
                    broken_links.append((v.get("id"), eq_id))

    if broken_links:
        print(f"❌ Migration Error: Found {len(broken_links)} broken equivalent_video_id links!")
        for b in broken_links[:5]:
            print(f"   Video ID '{b[0]}' references non-existent counterpart '{b[1]}'")
        return False

    # Save to disk
    with open(_CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f"💾 Saved Migrated Catalog to {_CATALOG_PATH}")
    print("\n" + "=" * 70)
    print("📊 MIGRATION & VALIDATION AUDIT SUMMARY")
    print("=" * 70)
    print(f"• Total Modules:               {len(catalog)}")
    print(f"• Total Topics:                {total_topics}")
    print(f"• Total Video Entities:        {total_videos}")
    print(f"• English Videos ('en'):       {stats['en']}")
    print(f"• Hindi Videos ('hi'):         {stats['hi']}")
    print(f"• Cross-Linked Pairs:          {stats['linked_pairs']} (100% bi-directional)")
    print(f"• Broken Equivalent FK Links:  0 (Verified)")
    print("\n📈 Taxonomy Level Breakdown:")
    for lvl, count in stats["levels"].items():
        print(f"  - {lvl:<14}: {count} videos")
    print("\n⏱️ Duration Category Breakdown:")
    for dur_cat, count in stats["duration_categories"].items():
        print(f"  - {dur_cat:<14}: {count} videos")

    print("\n" + "=" * 70)
    print("🔍 SAMPLE MIGRATED RECORDS PREVIEW")
    print("=" * 70)
    sample_topic = catalog[0]["topics"][0]
    print("\n[English Video Record]:")
    print(json.dumps(sample_topic["en"], indent=2, ensure_ascii=False))
    print("\n[Hindi Video Record (Cross-Linked Counterpart)]:")
    print(json.dumps(sample_topic["hi"], indent=2, ensure_ascii=False))

    print("\n✅ Video Database Schema Migration & Seeding Completed Successfully!")
    return True


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
