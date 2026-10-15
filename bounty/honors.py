"""Non-monetary medals: importance picks the element (点 / 线 / 面), urgency picks the palette."""
IMPORTANCE = {'light': '轻量', 'standard': '常规', 'major': '重要'}
URGENCY = {'normal': '不急', 'urgent': '加急'}
EFFORT = {'light': '半天内', 'standard': '一两天', 'major': '一周左右'}
# 点动成线，线动成面：任务越重，勋章填得越满；不急用冷色，加急用暖色并挂「急」角标。
MEDALS = {
    'light-normal': {'name': '点', 'hue': '#00A27A'},
    'standard-normal': {'name': '线', 'hue': '#00AEE0'},
    'major-normal': {'name': '面', 'hue': '#2866B1'},
    'light-urgent': {'name': '点·急', 'hue': '#F2B700'},
    'standard-urgent': {'name': '线·急', 'hue': '#F39800'},
    'major-urgent': {'name': '面·急', 'hue': '#E54465'},
}


def medal_key(task):
    return f"{task['importance']}-{task['urgency']}"


# 经验按工作量给：重要任务约等于八个轻量任务，愿意啃硬骨头的人升级更快；加急多 50%。
XP = {'light': 10, 'standard': 30, 'major': 80}
# 等了这么多天还没人接的任务算「冷门」：接下它的人完成后经验再多 20%
COLD_DAYS = 5
COLD_BONUS = 0.2


def task_xp(key):
    importance, urgency = key.split('-')
    base = XP[importance]
    return base + base // 2 if urgency == 'urgent' else base


def cold_bonus(key):
    return round(task_xp(key) * COLD_BONUS)
