import sys

file_path = r'quest_app\tabs\chat.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace Sent message risk
content = content.replace(
    '''<div class="label" style="margin-top:6px;">Risk</div>
                                    <div class="val">{pd_data.get('risk_score', 0):.0f} ({pd_data.get('risk_bucket', 'N/A')})</div>''',
    '''<div class="label" style="margin-top:6px;">Growth</div>
                                    <div class="val" style="color:{pnl_color}">{pd_data.get('growth_abs', 0):+,.0f}</div>'''
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
