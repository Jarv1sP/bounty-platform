"""縁側（游戏角）里的两个小游戏：随便玩，不花任何东西。有几样玩法和印章样式要靠勋章解锁（见 unlocks.py），
解锁了就一直在。游戏不给经验也不给勋章，只能解锁两个称号。凡是算数的结果都在服务器上检查。"""
import random
import zlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from .db import connect
from .service import TEAM_TZ, InvalidAction, now
from . import titles, unlocks

# 一笔画：用一笔走完所有的边（欧拉路径）。每关都保证有解：图连通，奇数度的点只有 0 个或 2 个。
# 坐标在 100×100 的画板上。
LEVELS = (
    ('一条线', ((18, 50), (50, 50), (82, 50)),
     ((0, 1), (1, 2))),
    ('三角', ((50, 18), (18, 80), (82, 80)),
     ((0, 1), (1, 2), (2, 0))),
    ('斜一刀', ((22, 22), (78, 22), (78, 78), (22, 78)),
     ((0, 1), (1, 2), (2, 3), (3, 0), (0, 2))),
    ('蝴蝶结', ((50, 50), (14, 22), (14, 78), (86, 22), (86, 78)),
     ((0, 1), (1, 2), (2, 0), (0, 3), (3, 4), (4, 0))),
    ('箭头', ((12, 50), (44, 50), (44, 22), (88, 50), (44, 78)),
     ((0, 1), (1, 2), (2, 3), (3, 4), (4, 1), (1, 3))),
    ('两格', ((14, 28), (50, 28), (86, 28), (14, 72), (50, 72), (86, 72)),
     ((0, 1), (1, 2), (3, 4), (4, 5), (0, 3), (1, 4), (2, 5))),
    ('小房子', ((24, 86), (76, 86), (76, 46), (24, 46), (50, 12)),
     ((0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3), (3, 4), (2, 4))),
    ('小鱼', ((12, 50), (42, 24), (42, 76), (66, 50), (90, 22), (90, 78)),
     ((0, 1), (1, 3), (3, 2), (2, 0), (3, 4), (4, 5), (5, 3), (0, 3))),
    ('星星', ((50, 16), (84.2, 40.9), (71.2, 81.1), (28.8, 81.1), (15.8, 40.9)),
     ((0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2), (1, 3), (2, 4), (3, 0), (4, 1))),
    ('龟壳', ((50, 14), (82.9, 33), (82.9, 71), (50, 90), (17.1, 71), (17.1, 33), (50, 52)),
     ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0), (6, 0), (6, 2), (6, 4), (0, 2))),
    ('灯塔', ((30, 90), (70, 90), (70, 62), (30, 62), (70, 36), (30, 36), (50, 12)),
     ((0, 1), (1, 2), (2, 3), (3, 0), (2, 4), (4, 5), (5, 3), (5, 6), (6, 4), (0, 2), (3, 4))),
    ('六角', ((50, 14), (82.9, 33), (82.9, 71), (50, 90), (17.1, 71), (17.1, 33)),
     ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0), (0, 2), (2, 4), (4, 0), (1, 3), (3, 5), (5, 1))),
    ('九宫', ((16, 16), (50, 16), (84, 16), (16, 50), (50, 50), (84, 50), (16, 84), (50, 84), (84, 84)),
     ((0, 1), (1, 2), (3, 4), (4, 5), (6, 7), (7, 8), (0, 3), (1, 4), (2, 5), (3, 6), (4, 7), (5, 8), (1, 3))),
    ('两间房', ((10, 86), (46, 86), (46, 50), (10, 50), (28, 22), (90, 86), (90, 50), (68, 22)),
     ((0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3), (3, 4), (4, 2), (1, 5), (5, 6), (6, 2), (2, 7), (7, 6))),
    ('满格', ((16, 16), (50, 16), (84, 16), (16, 50), (50, 50), (84, 50), (16, 84), (50, 84), (84, 84)),
     ((0, 1), (1, 2), (3, 4), (4, 5), (6, 7), (7, 8), (0, 3), (1, 4), (2, 5), (3, 6), (4, 7), (5, 8), (1, 3), (5, 7), (0, 4), (4, 8))),
)

FREE_LEVELS = 3     # 前三关直接开，之后画完一关开下一关

# 盖章挑战的玩法：越往后越快、越乱。unlock 是 unlocks.py 里的条目，None 表示一开始就能玩
MODES = {
    'normal': dict(name='普通', unlock=None, seconds=30, speed=1.0, urgent=0.18, void=0.15,
                   about='单子一张张来，看准中间盖。'),
    'rush': dict(name='加急日', unlock='mode:rush', seconds=30, speed=1.35, urgent=0.45, void=0.12,
                 about='一半是加急单，跑得快，分数也翻倍。'),
    'finals': dict(name='期末周', unlock='mode:finals', seconds=45, speed=1.2, urgent=0.3, void=0.25,
                   about='45 秒，单子成堆地来，退回的也多。'),
}
# 印章样式（只是好看）
STYLES = (('pass', '通过', None), ('good', '好', 'style:good'), ('great', '赞', 'style:great'), ('dlm', '点线面', 'style:dlm'))
GAME_TITLES = ('oneline', 'stamper')


def mode_open(have, mode):
    return MODES[mode]['unlock'] is None or MODES[mode]['unlock'] in have


def _new_game_titles(db, user_id):
    """Celebrate game titles right away on the game page (medal titles wait for the mailbox)."""
    fresh = [item for item in titles.unseen(db, user_id) if item['key'] in GAME_TITLES]
    db.executemany('INSERT OR IGNORE INTO titles_seen (user_id,key,seen_at) VALUES (?,?,?)',
                   [(user_id, item['key'], now()) for item in fresh])
    return [dict(key=item['key'], name=item['name'], how=item['how'], color=item['color']) for item in fresh]


# ---------- 一笔画 ----------
def lines_state(db, user_id):
    solved = {row['level'] for row in db.execute('SELECT level FROM lines_solved WHERE user_id=?', (user_id,))}
    open_levels = [n for n in range(1, len(LEVELS) + 1) if n <= FREE_LEVELS or n - 1 in solved]
    return dict(open=open_levels, solved=solved, total=len(LEVELS), random='random' in unlocks.unlocked(db, user_id))


def check_stroke(board, stroke):
    """True when the node sequence walks every edge exactly once, never jumping between unconnected dots."""
    _, nodes, edges = board
    if len(stroke) != len(edges) + 1 or any(not isinstance(n, int) or not 0 <= n < len(nodes) for n in stroke):
        return False
    return Counter(frozenset(pair) for pair in zip(stroke, stroke[1:])) == Counter(frozenset(edge) for edge in edges)


GRID = (12, 37, 63, 88)


def generate(seed, steps):
    """A fresh puzzle: the trace of a random walk on a 4×4 grid of dots (moves to any of the 8 neighbours, never
    reusing a line). The walk itself is a solution, so every generated puzzle can be drawn in one stroke."""
    rng = random.Random(seed)
    best = []
    for _ in range(40):
        position = (rng.randrange(4), rng.randrange(4))
        used, trail = [], [position]
        while len(used) < steps:
            x, y = position
            options = [(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx or dy)
                       and 0 <= x + dx < 4 and 0 <= y + dy < 4 and frozenset((position, (x + dx, y + dy))) not in used]
            if not options:
                break
            position = rng.choice(options)
            used.append(frozenset((trail[-1], position)))
            trail.append(position)
        if len(used) > len(best):
            best = used
        if len(best) >= steps:
            break
    points = sorted({point for edge in best for point in edge})
    index = {point: i for i, point in enumerate(points)}
    edges = [tuple(index[point] for point in sorted(edge)) for edge in best]
    rng.shuffle(edges)
    return (f'#{seed}', tuple((GRID[x], GRID[y]) for x, y in points), tuple(edges))


def today():
    """The team's calendar day: everyone gets the same daily puzzle whatever their time zone."""
    return datetime.now(timezone.utc).astimezone(TEAM_TZ).date().isoformat()


def daily_board(day):
    seed = zlib.crc32(f'daily-{day}'.encode())
    name, nodes, edges = generate(seed, 11 + seed % 5)
    return (f'{day[5:7]}/{day[8:]} 每日一笔', nodes, edges)


def random_board(seed):
    return generate(seed, 8 + seed % 9)


def board_for(db, user_id, kind, value):
    """(board, extra) for a fixed level, today's puzzle or a random one, or raise when it is not open yet."""
    state = lines_state(db, user_id)
    if kind == 'level':
        if value not in state['open']:
            raise InvalidAction(f'先画完第 {value - 1} 关，第 {value} 关就开了。')
        return LEVELS[value - 1]
    if kind == 'daily':
        return daily_board(today())
    if not state['random']:
        raise InvalidAction(f'随机一笔要{unlocks.need_text(unlocks.BY_ID["random"][3])}才开。')
    return random_board(value)


def solve(path, user_id, kind, value, stroke):
    with connect(path, write=True) as db:
        board = board_for(db, user_id, kind, value)
        if not check_stroke(board, stroke):
            raise InvalidAction('还没有一笔走完所有的线。')
        first = False
        if kind == 'level':
            first = not db.execute('SELECT 1 FROM lines_solved WHERE user_id=? AND level=?', (user_id, value)).fetchone()
            db.execute('INSERT OR IGNORE INTO lines_solved (user_id,level,solved_at) VALUES (?,?,?)', (user_id, value, now()))
        elif kind == 'daily':
            first = not db.execute('SELECT 1 FROM daily_solved WHERE user_id=? AND day=?', (user_id, today())).fetchone()
            db.execute('INSERT OR IGNORE INTO daily_solved (user_id,day,solved_at) VALUES (?,?,?)', (user_id, today(), now()))
        return dict(first=first, titles=_new_game_titles(db, user_id), state=lines_state(db, user_id),
                    daily=daily_count(db) if kind == 'daily' else None)


def daily_count(db, day=None):
    """How many teammates have drawn today's puzzle (no ranking, just company)."""
    return db.execute('SELECT COUNT(*) FROM daily_solved WHERE day=?', (day or today(),)).fetchone()[0]


# ---------- 盖章挑战 ----------
def stamp_caps(mode):
    """Upper bounds for one run: at most 2.4 slips a second, 300 points a slip at 3×."""
    slips = int(MODES[mode]['seconds'] * 2.4)
    return slips, slips * 300 * 3


def stamp_best(db, user_id):
    best = {key: dict(score=0, combo=0, runs=0) for key in MODES}
    for row in db.execute("""SELECT mode,MAX(score) score,MAX(combo) combo,COUNT(*) runs FROM game_runs
            WHERE user_id=? AND game='stamp' AND finished_at IS NOT NULL GROUP BY mode""", (user_id,)):
        if row['mode'] in best:
            best[row['mode']] = dict(score=row['score'] or 0, combo=row['combo'] or 0, runs=row['runs'])
    return best


def start_stamp(path, user_id, mode):
    """Free to play; the server only notes when the run started so it can check the result."""
    if mode not in MODES:
        raise InvalidAction('没有这种玩法。')
    with connect(path, write=True) as db:
        if not mode_open(unlocks.unlocked(db, user_id), mode):
            raise InvalidAction(f'「{MODES[mode]["name"]}」要{unlocks.need_text(unlocks.BY_ID[MODES[mode]["unlock"]][3])}才开。')
        cursor = db.execute("INSERT INTO game_runs (user_id,game,mode,started_at) VALUES (?,'stamp',?,?)", (user_id, mode, now()))
        return cursor.lastrowid


def finish_stamp(path, user_id, run_id, score, combo):
    """Record a run. The server knows when it started, so a run cannot be shorter than the game or replayed."""
    with connect(path, write=True) as db:
        run = db.execute("SELECT * FROM game_runs WHERE id=? AND user_id=? AND game='stamp'", (run_id, user_id)).fetchone()
        if not run or run['finished_at']:
            raise InvalidAction('这一局已经结束了。')
        mode = run['mode'] if run['mode'] in MODES else 'normal'
        seconds = MODES[mode]['seconds']
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(run['started_at'])).total_seconds()
        if elapsed < seconds - 3 or elapsed > 15 * 60:
            raise InvalidAction('这一局的时间不对，没有记录。')
        max_slips, max_score = stamp_caps(mode)
        if not (0 <= score <= max_score and 0 <= combo <= max_slips):
            raise InvalidAction('分数不对，没有记录。')
        before = stamp_best(db, user_id)[mode]
        db.execute('UPDATE game_runs SET finished_at=?,score=?,combo=? WHERE id=?', (now(), score, combo, run_id))
        # 最近 20 分钟玩了几局：玩多了结算页会轻轻提醒一句
        recent = db.execute("""SELECT COUNT(*) FROM game_runs WHERE user_id=? AND finished_at>?""",
                            (user_id, (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat())).fetchone()[0]
        return dict(best=stamp_best(db, user_id)[mode], record=score > before['score'] and before['runs'] > 0,
                    titles=_new_game_titles(db, user_id), recent=recent)
