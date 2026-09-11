import os
import sys
import tempfile
import shutil
from datetime import datetime, timezone, timedelta

# Ensure workspace root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import edu_db
import firebase_db

def test_edu_db_defaults_and_sections():
    print("Testing edu_db defaults and section migration...")
    temp_dir = tempfile.mkdtemp()
    try:
        edu_db.set_data_dir(temp_dir, "testuser")
        prog = edu_db.load_progress()
        assert "quest_coins" in prog, "quest_coins missing from DEFAULT_PROGRESS"
        assert "entitlements" in prog, "entitlements missing from DEFAULT_PROGRESS"
        assert prog["quest_coins"] == 0
        assert prog["entitlements"] == {}

        # Test set and get education section
        edu_db.set_last_education_section("Shop")
        assert edu_db.get_last_education_section() == "Shop", "Failed to set/get Shop in edu"

        # Test legacy Wallet migration in edu
        edu_db.set_last_education_section("Wallet")
        assert edu_db.get_last_education_section() == "Shop", "Wallet should migrate to Shop in edu"

        # Test set and get portfolio section
        edu_db.set_last_portfolio_section("Shop")
        assert edu_db.get_last_portfolio_section() == "Shop", "Failed to set/get Shop in portfolio"

        # Test legacy Wallet migration in portfolio
        edu_db.set_last_portfolio_section("Wallet")
        assert edu_db.get_last_portfolio_section() == "Shop", "Wallet should migrate to Shop in portfolio"
        print("[OK] edu_db defaults and section migration passed!")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_entitlements_backend():
    print("Testing firebase_db entitlements backend...")
    import uuid
    test_user = f"test_user_{uuid.uuid4().hex[:8]}"
    temp_dir = tempfile.mkdtemp()
    try:
        edu_db.set_data_dir(temp_dir, test_user)
        prog = edu_db.load_progress()
        prog["quest_coins"] = 5000
        edu_db.save_progress(prog)

        assert hasattr(firebase_db, "STANDARD_ENTITLEMENT_KEYS"), "STANDARD_ENTITLEMENT_KEYS missing"
        expected_keys = ["premium", "ad_free", "news_access", "intl_stocks"]
        for k in expected_keys:
            assert k in firebase_db.STANDARD_ENTITLEMENT_KEYS, f"{k} not in STANDARD_ENTITLEMENT_KEYS"

        # 1. Initial state check
        ents = firebase_db.get_user_entitlements(test_user)
        for k in expected_keys:
            assert k in ents
            assert ents[k] is None
            assert not firebase_db.has_entitlement(test_user, k)

        # 2. Grant entitlement with coin deduction
        ok, msg, data = firebase_db.grant_entitlement(test_user, "ad_free", duration_days=30, cost_coins=500)
        assert ok, f"Grant entitlement failed: {msg}"
        assert data["new_coins_balance"] == 4500, f"Expected 4500 coins, got {data['new_coins_balance']}"
        assert firebase_db.has_entitlement(test_user, "ad_free"), "User should have ad_free entitlement"

        # Check local edu_db mirroring
        local_prog = edu_db.load_progress()
        assert local_prog["quest_coins"] == 4500
        assert "ad_free" in local_prog.get("entitlements", {})
        assert local_prog["entitlements"]["ad_free"] == data["expires_at"]

        # 3. Grant extension (extending existing active entitlement)
        first_expiry = datetime.fromisoformat(data["expires_at"])
        ok2, msg2, data2 = firebase_db.grant_entitlement(test_user, "ad_free", duration_days=15, cost_coins=200)
        assert ok2
        assert data2["new_coins_balance"] == 4300
        second_expiry = datetime.fromisoformat(data2["expires_at"])
        diff_days = (second_expiry.date() - first_expiry.date()).days
        assert diff_days == 15, f"Expected 15 day extension, got {diff_days}"

        # 4. Insufficient coins check
        ok3, msg3, data3 = firebase_db.grant_entitlement(test_user, "intl_stocks", duration_days=30, cost_coins=10000)
        assert not ok3, "Should fail when coins are insufficient"
        assert not firebase_db.has_entitlement(test_user, "intl_stocks")

        # 5. Test expired entitlement
        expired_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        local_prog = edu_db.load_progress()
        local_prog["entitlements"]["news_access"] = expired_date
        edu_db.save_progress(local_prog)

        assert not firebase_db.has_entitlement(test_user, "news_access"), "Expired entitlement should return False"

        print("[OK] firebase_db entitlements backend passed!")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_shop_tab_imports():
    print("Testing quest_app.tabs.shop import and helpers...")
    import quest_app.tabs.shop as shop_tab
    assert hasattr(shop_tab, "render")
    assert hasattr(shop_tab, "_create_payment_link")
    print("[OK] quest_app.tabs.shop import passed!")


def test_main_navigation_and_pages():
    print("Testing main.py valid pages and labels configuration...")
    # Inspect main.py directly to verify valid_pages and labels
    main_py_path = os.path.join(os.path.dirname(__file__), "..", "quest_app", "main.py")
    with open(main_py_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    assert '"Shop"' in content
    assert '"Shop": "🛒  Shop"' in content
    assert 'section in ("Shop", "Wallet")' in content
    assert 'import quest_app.tabs.shop as tb' in content
def test_enforcements():
    print("Testing ad_free and news_access enforcements...")
    import quest_app.tabs.edu_overview as edu_tab
    import quest_app.tabs.news as news_tab

    # Verify functions exist
    assert hasattr(edu_tab, "_render_ad_banner")
    assert hasattr(news_tab, "render")
    print("[OK] Enforcement modules imported and verified!")


def test_module_completion():
    print("Testing edu_db.is_module_completed...")
    temp_dir = tempfile.mkdtemp()
    try:
        edu_db.set_data_dir(temp_dir, "testuser_mod")
        # 1. Empty progress -> False
        assert not edu_db.is_module_completed("module_5")

        # 2. Fast path: module_5 directly in completed_levels
        prog = edu_db.load_progress()
        prog["completed_levels"] = ["module_5"]
        edu_db.save_progress(prog)
        assert edu_db.is_module_completed("module_5")

        # 3. Slow path: all topic titles completed
        prog["completed_levels"] = [
            'Asset Allocation — The Biggest Decision',
            'Diversified Portfolio in India',
            'Equity + Debt + Gold Mix by Age',
            'Portfolio Rebalancing',
            'Large Cap vs Mid Cap vs Small Cap',
            'Core Satellite Portfolio',
            'How Many Stocks Should You Hold',
            'ETFs vs Mutual Funds vs Stocks',
            'International Diversification',
            'Sample ₹10 Lakh Portfolio'
        ]
        edu_db.save_progress(prog)
        assert edu_db.is_module_completed("module_5")
        print("[OK] is_module_completed passed!")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    test_edu_db_defaults_and_sections()
    test_entitlements_backend()
    test_shop_tab_imports()
    test_main_navigation_and_pages()
    test_enforcements()
    test_module_completion()
    print("\nALL TESTS PASSED SUCCESSFULLY!")
