import sys
sys.path.append('.')
from pixel_assistant_app.config import ConfigManager
from pixel_assistant_app.brain import AIBrain
c = ConfigManager()
print('config max_reply_chars:', c.get('max_reply_chars'))
# Create AIBrain without API key to avoid network calls
b = AIBrain(api_key=None, max_reply_chars=c.get('max_reply_chars'))
print('AIBrain max_reply_chars:', getattr(b, 'max_reply_chars', None))
