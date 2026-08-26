import sys

file_path = r'quest_app\tabs\chat.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace sender name with anchor
content = content.replace(
    '''sender = msg["from"]
                            bubble = f'<div class="chat-bubble received"><div class="chat-sender">{sender}</div>{msg["text"]}' ''',
    '''sender = msg["from"]
                            bubble = f'<div class="chat-bubble received"><div class="chat-sender"><a href="?page=Chat&view_profile={sender}" target="_self" style="text-decoration:none;color:inherit;">{sender}</a></div>{msg["text"]}' '''
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
