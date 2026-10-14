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
