import sys
import re

file_path = 'chat_system.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

new_func = '''def build_portfolio_snapshot(df, summary: dict, username: str) -> dict:
    if df is None or df.empty:
        return {
            "username": username,
            "timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
            "total_value": 0, "total_pnl": 0, "pnl_pct": 0,
            "n_assets": 0, "growth_abs": 0, "growth_pct": 0,
            "top_holdings": [],
        }

    from risk_analyzer import get_portfolio_growth
    growth = get_portfolio_growth(df, summary)
    
    total_invested = float(df["Invested (₹)"].sum())
    total_pnl = float(df["P&L (₹)"].sum())

    top = df.nlargest(5, "Current Value (₹)")
    top_holdings = []
    for _, row in top.iterrows():
        top_holdings.append({
            "name": str(row["Name"]) if "Name" in row else str(row.get("Asset Name", "")),
            "value": float(row["Current Value (₹)"]),
            "pnl_pct": float(row["P&L %"]) if "P&L %" in row else 0,
        })

    return {
        "username": username,
        "timestamp": datetime.now(pytz.timezone('Asia/Kolkata')).isoformat(),
        "total_value": float(summary.get("total_value", 0)),
        "total_invested": total_invested,
        "total_pnl": total_pnl,
        "pnl_pct": (total_pnl / total_invested * 100) if total_invested > 0 else 0,
        "n_assets": int(summary.get("n_assets", 0)),
        "growth_abs": float(growth["growth_abs"]),
        "growth_pct": float(growth["growth_pct"]),
        "top_holdings": top_holdings
    }'''

pattern = re.compile(r'def build_portfolio_snapshot.*?return \{.*?top_holdings.*?\}', re.DOTALL)
content = pattern.sub(new_func, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
