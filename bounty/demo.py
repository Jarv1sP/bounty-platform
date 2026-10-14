"""Generate an independent, editable local demo database. Never reads workspace users."""
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash
from .db import connect, initialize
from .service import create_task, act

DEMO_USERS = ('发布者', '认领人', '其他成员')
DEMO_PASSWORD = 'demo12345'
TITLES = (
    ('算法复现', '跑通图像分类 baseline'), ('论文阅读', '整理一篇论文的方法与假设'), ('工程支持', '补充数据读取单元测试'),
    ('实验分析', '检查三组实验的评估口径'), ('分享整理', '整理组会讨论与待办'), ('算法复现', '核对训练配置与官方实现'),
    ('工程支持', '修复可视化脚本的字体问题'), ('论文阅读', '整理相关工作的对照表'), ('实验分析', '检查数据划分是否有重复'),
    ('分享整理', '准备新成员环境配置说明'), ('工程支持', '补充训练日志导出'), ('实验分析', '整理失败实验的排查记录'),
    ('论文阅读', '解释论文中的核心损失函数'), ('分享整理', '准备一次代码走读'), ('算法复现', '核对推理与预处理步骤'),
    ('工程支持', '补齐 README 中的运行示例'), ('分享整理', '整理公开数据集使用说明'), ('论文阅读', '汇总论文实现中的未明确细节'),
    ('工程支持', '统一结果表格的字段'), ('实验分析', '检查训练与验证集标签分布'), ('算法复现', '记录复现实验的配置差异'),
    ('分享整理', '整理可复用的组会模板'), ('实验分析', '定位复现差异的可能原因'), ('工程支持', '补齐数据检查工具和说明'),
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
            act(path, task_id, 2, 'submit', '演示交付：已整理步骤、运行记录与限制；发现的问题和未完成验证均已注明。')
        if index >= 22:
            act(path, task_id, 1, 'accept', '排查记录把配置差异和待验证项分清了，后续复现可以直接接着做。' if index == 22 else '谢谢补齐检查工具与使用说明，新成员也能独立排查数据问题了。')
    return len(TITLES)
