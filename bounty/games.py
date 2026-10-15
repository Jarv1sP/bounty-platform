"""游戏角: short games unlocked by real work. Game tickets come only from accepted tasks; games never give experience
or medals, only titles. Every result that matters is checked on the server."""
from collections import Counter
from datetime import datetime, timezone
from .db import STARTER_TICKETS, connect
from .service import InvalidAction, now
from . import titles

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
STAMP_SECONDS = 30
# 盖章挑战的上限：30 秒里最多出 70 张单子，每张最多 300 分、最高 3 倍，连击不会超过单子数
STAMP_MAX_SLIPS = 70
STAMP_MAX_SCORE = STAMP_MAX_SLIPS * 300 * 3
GAME_TITLES = ('oneline', 'stamper')


def balance(db, user_id):
    return STARTER_TICKETS + (db.execute('SELECT COALESCE(SUM(delta),0) FROM tickets WHERE user_id=?', (user_id,)).fetchone()[0])


def spend(db, user_id, reason, ref=None):
    """Use one ticket inside the caller's write transaction."""
    if balance(db, user_id) < 1:
        raise InvalidAction('游戏券用完了。验收通过一个任务就有新的券。')
    db.execute('INSERT INTO tickets (user_id,delta,reason,ref,created_at) VALUES (?,-1,?,?,?)', (user_id, reason, ref, now()))


def _new_game_titles(db, user_id):
    """Celebrate game titles right away on the game page (medal titles wait for the mailbox)."""
    fresh = [item for item in titles.unseen(db, user_id) if item['key'] in GAME_TITLES]
    db.executemany('INSERT OR IGNORE INTO titles_seen (user_id,key,seen_at) VALUES (?,?,?)',
                   [(user_id, item['key'], now()) for item in fresh])
    return [dict(key=item['key'], name=item['name'], how=item['how'], color=item['color']) for item in fresh]


# ---------- 一笔画 ----------
def lines_state(db, user_id):
    unlocked = 1 + db.execute("SELECT COUNT(*) FROM tickets WHERE user_id=? AND reason='lines'", (user_id,)).fetchone()[0]
    solved = {row['level'] for row in db.execute('SELECT level FROM lines_solved WHERE user_id=?', (user_id,))}
    return dict(unlocked=min(unlocked, len(LEVELS)), solved=solved, total=len(LEVELS))


def unlock_level(path, user_id):
    """Open the next level for one ticket. Only after the current last level is solved, so tickets are not wasted."""
    with connect(path, write=True) as db:
        state = lines_state(db, user_id)
        if state['unlocked'] >= len(LEVELS):
            raise InvalidAction('已经全部解锁了。')
        if state['unlocked'] not in state['solved']:
            raise InvalidAction('先把这一关画完，再解锁下一关。')
        spend(db, user_id, 'lines', str(state['unlocked'] + 1))
        return state['unlocked'] + 1


def check_stroke(level, stroke):
    """True when the node sequence walks every edge of the level exactly once, never jumping between unconnected dots."""
    _, nodes, edges = LEVELS[level - 1]
    if len(stroke) != len(edges) + 1 or any(not isinstance(n, int) or not 0 <= n < len(nodes) for n in stroke):
        return False
    need = Counter(frozenset(edge) for edge in edges)
    used = Counter(frozenset(pair) for pair in zip(stroke, stroke[1:]))
    return used == need


def solve_level(path, user_id, level, stroke):
    with connect(path, write=True) as db:
        if not 1 <= level <= lines_state(db, user_id)['unlocked']:
            raise InvalidAction('这一关还没解锁。')
        if not check_stroke(level, stroke):
            raise InvalidAction('还没有一笔走完所有的线。')
        first = not db.execute('SELECT 1 FROM lines_solved WHERE user_id=? AND level=?', (user_id, level)).fetchone()
        db.execute('INSERT OR IGNORE INTO lines_solved (user_id,level,solved_at) VALUES (?,?,?)', (user_id, level, now()))
        return dict(first=first, titles=_new_game_titles(db, user_id), state=lines_state(db, user_id))


# ---------- 盖章挑战 ----------
def stamp_best(db, user_id):
    row = db.execute("""SELECT MAX(score) score,MAX(combo) combo,COUNT(*) runs FROM game_runs
        WHERE user_id=? AND game='stamp' AND finished_at IS NOT NULL""", (user_id,)).fetchone()
    return dict(score=row['score'] or 0, combo=row['combo'] or 0, runs=row['runs'])


def start_stamp(path, user_id):
    with connect(path, write=True) as db:
        spend(db, user_id, 'stamp')
        cursor = db.execute("INSERT INTO game_runs (user_id,game,started_at) VALUES (?,'stamp',?)", (user_id, now()))
        return cursor.lastrowid


def finish_stamp(path, user_id, run_id, score, combo):
    """Record a run. The server knows when it started, so a run cannot be shorter than the game or replayed."""
    with connect(path, write=True) as db:
        run = db.execute("SELECT * FROM game_runs WHERE id=? AND user_id=? AND game='stamp'", (run_id, user_id)).fetchone()
        if not run or run['finished_at']:
            raise InvalidAction('这一局已经结束了。')
        elapsed = (datetime.now(timezone.utc) - datetime.fromisoformat(run['started_at'])).total_seconds()
        if elapsed < STAMP_SECONDS - 3 or elapsed > 15 * 60:
            raise InvalidAction('这一局的时间不对，没有记录。')
        if not (0 <= score <= STAMP_MAX_SCORE and 0 <= combo <= STAMP_MAX_SLIPS):
            raise InvalidAction('分数不对，没有记录。')
        before = stamp_best(db, user_id)
        db.execute('UPDATE game_runs SET finished_at=?,score=?,combo=? WHERE id=?', (now(), score, combo, run_id))
        return dict(best=stamp_best(db, user_id), record=score > before['score'] and before['runs'] > 0,
                    titles=_new_game_titles(db, user_id))
