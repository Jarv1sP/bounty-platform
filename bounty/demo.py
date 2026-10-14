"""Generate an independent, editable local demo database. Never reads workspace users."""
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash
from .db import connect, initialize
from .service import create_task, act

DEMO_USERS = ('发布者', '认领人', '其他成员')
DEMO_PASSWORD = 'demo12345'
TITLES = (
    ('文档', '整理新成员入门指南'), ('设计', '设计团队分享会海报'), ('开发', '补充文件导出工具'),
    ('调研', '比较三款录屏工具'), ('文档', '补充接口使用示例'), ('设计', '制作项目封面'),
    ('开发', '添加数据去重功能'), ('调研', '收集团队反馈'), ('文档', '翻译快速入门说明'),
    ('设计', '整理配色与字体规范'), ('开发', '优化搜索结果排序'), ('调研', '调研文档协作工具'),
    ('文档', '归档分享会笔记'), ('设计', '制作分类图标'), ('开发', '补充异常处理'),
    ('调研', '整理交付流程'), ('运营', '准备活动签到表'), ('其他', '整理会议室物品清单'),
    ('文档', '校对项目介绍'), ('开发', '制作批量重命名脚本'), ('运营', '整理分享会日程'),
    ('设计', '绘制活动签到卡'), ('文档', '整理常用命令速查表'), ('其他', '检查物料准备情况'),
)


def seed_demo(path):
    initialize(path)
    with connect(path, write=True) as db:
        if db.execute('SELECT COUNT(*) FROM users').fetchone()[0] or db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]:
            raise ValueError('演示数据只允许导入空数据库，请使用新的 --data-dir。')
        db.executemany('INSERT INTO users(name,password) VALUES (?,?)',
                       [(name, generate_password_hash(DEMO_PASSWORD)) for name in DEMO_USERS])
    importance = ('light', 'standard', 'major')
    deadline = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(timespec='seconds')
    for index, (category, title) in enumerate(TITLES):
        task_id = create_task(path, 1, dict(
            title=title, category=category, description='演示任务：' + title + '。请在任务内讨论具体需求，并按交付要求提交成果。',
            requirements='提交文字说明和成果链接；发布者检查完整性后验收，需要修改时说明原因。',
            importance=importance[index % 3], urgency='urgent' if index % 4 == 1 else 'normal', deadline=deadline,
        ))
        if index >= 16:
            act(path, task_id, 2, 'claim')
        if index >= 20:
            act(path, task_id, 2, 'submit', '演示交付：文档草稿已整理，请验收。')
        if index >= 22:
            act(path, task_id, 1, 'accept', '演示验收通过。')
    return len(TITLES)
