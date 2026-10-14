"""Small, non-monetary honors assigned by task scope and urgency."""
IMPORTANCE = {'light': '轻量', 'standard': '常规', 'major': '重要'}
URGENCY = {'normal': '不急', 'urgent': '加急'}
MEDALS = {
    'light-normal': {'name': '四叶草', 'symbol': 'clover', 'tone': 'mint'},
    'standard-normal': {'name': '饭团', 'symbol': 'rice', 'tone': 'blue'},
    'major-normal': {'name': '山樱', 'symbol': 'sakura', 'tone': 'blush'},
    'light-urgent': {'name': '晴天娃娃', 'symbol': 'sunny', 'tone': 'blue'},
    'standard-urgent': {'name': '纸鹤', 'symbol': 'crane', 'tone': 'coral'},
    'major-urgent': {'name': '流星', 'symbol': 'star', 'tone': 'blush'},
}


def medal_key(task):
    return f"{task['importance']}-{task['urgency']}"
