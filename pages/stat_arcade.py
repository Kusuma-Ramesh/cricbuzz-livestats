"""Stat Arcade: two quick games that turn the dataset into trivia (score, streak, XP)."""

import random

import streamlit as st

from services import analytics
from utils import theme
from utils.db_connection import run_query

theme.hero(
    "Arcade",
    "Think you know the numbers?",
    "Higher or Lower on career stats, plus a Guess-the-Total challenge. Streaks multiply your XP.",
)

S = st.session_state
for k, v in {
    "xp": 0,
    "streak": 0,
    "best": 0,
    "hl": None,
    "gt": None,
    "hl_msg": "",
    "gt_msg": "",
}.items():
    S.setdefault(k, v)
LEVELS = [
    (0, "Net bowler"),
    (60, "Club regular"),
    (160, "County pro"),
    (320, "Test debutant"),
    (560, "Captain"),
    (900, "Legend"),
]
level = [n for t, n in LEVELS if S.xp >= t][-1]
nxt = next((t for t, _ in LEVELS if t > S.xp), None)
theme.kpi_row(
    [
        ("XP", f"{S.xp}", level, "#E8A33D"),
        ("Streak", str(S.streak), "in a row", "#E879F9"),
        ("Best streak", str(S.best), "this session", "#14B8A6"),
    ],
    cols=3,
)
if nxt:
    st.progress(min(S.xp / nxt, 1.0), text=f"{S.xp} / {nxt} XP to next level")


def award(correct: bool, base: int) -> int:
    if correct:
        S.streak += 1
        S.best = max(S.best, S.streak)
        gain = base * (1 + min(S.streak - 1, 4) * 0.25)
        S.xp += int(gain)
        return int(gain)
    S.streak = 0
    return 0


ratings = analytics.player_ratings()
g1, g2 = st.columns(2)

# ---------------------------------------------------------------- Higher or Lower
with g1:
    theme.render(
        '<div class="cb-card"><h3 style="margin:0">Higher or Lower</h3>'
        '<p style="color:var(--ink-2);margin:4px 0 0">Who has more career runs?</p></div>'
    )
    if S.hl is None:
        a, b = random.sample(range(len(ratings)), 2)
        S.hl = (ratings.iloc[a].to_dict(), ratings.iloc[b].to_dict())
    pa, pb = S.hl
    st.markdown(f"**{pa['full_name']}** ({pa['country']}) - **{int(pa['runs']):,}** runs")
    st.markdown(f"vs **{pb['full_name']}** ({pb['country']}) - ?")
    c1, c2, c3 = st.columns(3)
    guess = (
        "higher"
        if c1.button("Higher", width="stretch")
        else "lower"
        if c2.button("Lower", width="stretch")
        else None
    )
    if guess:
        right = (pb["runs"] >= pa["runs"]) == (guess == "higher")
        gain = award(right, 10)
        S.hl_msg = (
            f"Correct! {pb['full_name']} has {int(pb['runs']):,} runs. +{gain} XP"
            if right
            else f"Not quite - {pb['full_name']} has {int(pb['runs']):,} runs."
        )
        S.hl = None
        st.rerun()
    if S.hl_msg:
        st.info(S.hl_msg)

# ---------------------------------------------------------------- Guess the total
with g2:
    theme.render(
        '<div class="cb-card"><h3 style="margin:0">Guess the Total</h3>'
        '<p style="color:var(--ink-2);margin:4px 0 0">Closer guesses earn more XP.</p></div>'
    )
    if S.gt is None:
        row = run_query(
            "SELECT m.match_id, m.description, m.match_format, SUM(b.runs) AS total FROM batting_performances b "
            "JOIN matches m ON m.match_id = b.match_id WHERE b.innings_no = 1 AND m.match_format <> 'Test' "
            "GROUP BY m.match_id, m.description, m.match_format ORDER BY RANDOM() LIMIT 1"
        )
        S.gt = row.iloc[0].to_dict() if not row.empty else None
    if S.gt:
        st.markdown(f"**{S.gt['description']}** - first-innings total?")
        top = 280 if S.gt["match_format"] == "T20I" else 400
        guess = st.slider("Your guess", 40, top, top // 2)
        if st.button("Lock it in", type="primary"):
            err = abs(guess - int(S.gt["total"]))
            pts = max(0, 50 - err)
            S.xp += pts
            S.gt_msg = f"Actual total: {int(S.gt['total'])} (you were {err} off) - +{pts} XP"
            S.gt = None
            st.rerun()
    if S.gt_msg:
        st.info(S.gt_msg)
