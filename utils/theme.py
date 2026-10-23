"""Design system for Cricbuzz LiveStats: tokens, CSS and HTML component builders.

Visual language: floodlit-stadium night palette (navy surfaces, teal + gold accents),
glass cards, tabular numerals, motion with a reduced-motion escape hatch.
All text coming from APIs/DB is HTML-escaped before it reaches the page.
"""

from __future__ import annotations

import html
import zlib
from typing import Iterable

import streamlit as st

TOKENS = dict(
    bg="#0B1220",
    card="#131C2E",
    card2="#182238",
    line="#1F2C42",
    line2="#2A3A55",
    ink="#E5E7EB",
    ink2="#8A97AB",
    ink3="#64748B",
    accent="#14B8A6",
    accent_dim="#0F766E",
    gold="#E8A33D",
    magenta="#E879F9",
    good="#3FB950",
    bad="#F0616D",
    blue="#60A5FA",
)
COLORWAY = [
    TOKENS["accent"],
    TOKENS["gold"],
    TOKENS["magenta"],
    TOKENS["blue"],
    TOKENS["good"],
    TOKENS["bad"],
    "#A78BFA",
    "#F59E0B",
]

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{--bg:#0B1220;--card:#131C2E;--card-2:#182238;--line:#1F2C42;--line-2:#2A3A55;--ink:#E5E7EB;--ink-2:#8A97AB;--ink-3:#64748B;
--accent:#14B8A6;--accent-dim:#0F766E;--gold:#E8A33D;--magenta:#E879F9;--good:#3FB950;--bad:#F0616D;--blue:#60A5FA;
--r:16px;--r-sm:10px;--t:200ms cubic-bezier(.4,0,.2,1);--font:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
html,body,.stApp{font-family:var(--font)}
.stApp{background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased}
.stApp::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;background:
radial-gradient(900px 520px at 6% -8%,rgba(20,184,166,.20),transparent 60%),
radial-gradient(820px 480px at 100% -6%,rgba(232,163,61,.15),transparent 60%),
radial-gradient(760px 520px at 55% 125%,rgba(232,121,249,.09),transparent 60%),
linear-gradient(rgba(255,255,255,.018) 1px,transparent 1px) 0 0/48px 48px,
linear-gradient(90deg,rgba(255,255,255,.018) 1px,transparent 1px) 0 0/48px 48px}
header[data-testid="stHeader"]{background:transparent}
#MainMenu,footer,[data-testid="stToolbar"],.stDeployButton,[data-testid="stDecoration"]{display:none!important;visibility:hidden}
.block-container{max-width:1360px;padding:1rem 1.6rem 4rem;position:relative;z-index:1}
h1,h2,h3,h4{letter-spacing:-.02em;color:var(--ink)}
.tnum,.cb-kpi b,.cb-score,.cb-stat b{font-variant-numeric:tabular-nums}
*:focus-visible{outline:2px solid var(--accent)!important;outline-offset:2px}
/* sidebar */
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#0E1627,#0B1220);border-right:1px solid var(--line)}
[data-testid="stSidebarNav"]::before{content:"CRICBUZZ LIVESTATS";display:block;margin:6px 16px 10px;font-size:11px;font-weight:800;letter-spacing:.16em;color:var(--accent)}
[data-testid="stSidebarNav"] a{border-radius:10px;margin:2px 10px;transition:background var(--t),transform var(--t)}
[data-testid="stSidebarNav"] a:hover{background:var(--card-2)}
[data-testid="stSidebarNav"] a[aria-current="page"]{background:linear-gradient(90deg,rgba(20,184,166,.22),rgba(20,184,166,.04));box-shadow:inset 3px 0 0 var(--accent)}
[data-testid="stSidebarNav"] a span{font-weight:600;font-size:13.5px}
/* widgets */
.stTabs [data-baseweb="tab-list"]{gap:6px;border-bottom:1px solid var(--line)}
.stTabs [data-baseweb="tab"]{height:40px;padding:0 16px;border-radius:10px 10px 0 0;color:var(--ink-2);font-weight:600}
.stTabs [aria-selected="true"]{color:var(--ink)!important;background:linear-gradient(180deg,transparent,rgba(20,184,166,.12))}
.stTabs [data-baseweb="tab-highlight"]{background:var(--accent);height:3px;border-radius:3px}
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{border-radius:var(--r-sm);border:1px solid var(--line-2);background:var(--card-2);color:var(--ink);font-weight:600;transition:all var(--t)}
.stButton>button:hover,.stDownloadButton>button:hover,.stFormSubmitButton>button:hover{border-color:var(--accent);color:#fff;transform:translateY(-1px);box-shadow:0 6px 18px rgba(20,184,166,.18)}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"],.stFormSubmitButton>button[kind="primaryFormSubmit"]{background:linear-gradient(135deg,#14B8A6,#0F766E);border-color:transparent;color:#fff}
[data-baseweb="input"],[data-baseweb="base-input"],[data-baseweb="select"]>div,[data-baseweb="textarea"],.stNumberInput [data-baseweb="input"]{background:var(--card-2)!important;border-color:var(--line-2)!important;border-radius:var(--r-sm)!important}
.stTextArea textarea{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:var(--r);overflow:hidden}
[data-testid="stExpander"]{border:1px solid var(--line);border-radius:var(--r);background:var(--card)}
[data-testid="stForm"]{border:1px solid var(--line);border-radius:var(--r);background:linear-gradient(180deg,var(--card),#101828);padding:18px}
[data-testid="stAlert"]{border-radius:var(--r-sm)}
.stPlotlyChart{border-radius:var(--r)}
.stPlotlyChart svg text,.stPlotlyChart svg tspan{letter-spacing:normal;text-transform:none;line-height:normal}
.stPlotlyChart .js-plotly-plot .plotly .main-svg{overflow:visible!important}
pre,code{border-radius:var(--r-sm)!important}
label,[data-testid="stWidgetLabel"] p{color:var(--ink-2)!important;font-size:12px!important;font-weight:700!important;letter-spacing:.06em;text-transform:uppercase}
/* HUD */
.cb-hud{display:flex;align-items:center;gap:22px;flex-wrap:wrap;padding:12px 18px;border:1px solid var(--line);border-radius:var(--r);background:rgba(19,28,46,.72);backdrop-filter:blur(14px);margin-bottom:12px}
.cb-brand{display:flex;align-items:center;gap:12px;margin-right:auto}
.cb-brand svg{width:34px;height:34px;animation:spin 14s linear infinite}
.cb-brand h1{margin:0;font-size:19px;font-weight:800;line-height:1.1;padding:0}
.cb-brand span{display:block;font-size:10.5px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.12em;font-weight:700}
.cb-stat{display:flex;flex-direction:column;gap:1px;min-width:62px}
.cb-stat b{font-size:18px;font-weight:700;line-height:1.1}.cb-stat.gold b{color:var(--gold)}.cb-stat.teal b{color:var(--accent)}
.cb-stat i{font-style:normal;font-size:10px;color:var(--ink-3);text-transform:uppercase;letter-spacing:.09em;font-weight:700}
/* ticker */
.cb-ticker{overflow:hidden;white-space:nowrap;border:1px solid var(--line);border-radius:999px;background:rgba(11,18,32,.8);margin-bottom:18px;position:relative}
.cb-ticker::before,.cb-ticker::after{content:"";position:absolute;top:0;bottom:0;width:60px;z-index:2;pointer-events:none}
.cb-ticker::before{left:0;background:linear-gradient(90deg,var(--bg),transparent)}.cb-ticker::after{right:0;background:linear-gradient(270deg,var(--bg),transparent)}
.cb-track{display:inline-flex;gap:38px;padding:9px 0;animation:marquee 60s linear infinite}
.cb-ticker:hover .cb-track{animation-play-state:paused}
.cb-tick{font-size:12.5px;color:var(--ink-2);font-weight:600}.cb-tick b{color:var(--ink)}.cb-tick em{font-style:normal;color:var(--gold)}
/* hero */
.cb-hero{position:relative;overflow:hidden;border:1px solid var(--line-2);border-radius:22px;padding:34px 36px;margin-bottom:20px;background:
radial-gradient(600px 260px at 90% 0%,rgba(232,163,61,.22),transparent 70%),radial-gradient(520px 300px at 0% 100%,rgba(20,184,166,.24),transparent 70%),linear-gradient(135deg,#15213A,#0F1728);animation:fadeUp .6s both}
.cb-hero::after{content:"";position:absolute;right:-60px;top:-60px;width:260px;height:260px;border-radius:50%;border:2px solid rgba(255,255,255,.06);box-shadow:0 0 0 38px rgba(255,255,255,.02),0 0 0 80px rgba(255,255,255,.015)}
.cb-kicker{font-size:11px;font-weight:800;letter-spacing:.18em;text-transform:uppercase;color:var(--accent)}
.cb-hero h2{font-size:clamp(26px,3.4vw,42px);font-weight:800;margin:8px 0 8px;line-height:1.08;background:linear-gradient(90deg,#fff,#9FB3D1 60%,var(--gold));-webkit-background-clip:text;background-clip:text;color:transparent}
.cb-hero p{max-width:760px;color:var(--ink-2);font-size:15px;line-height:1.6;margin:0 0 14px}
/* generic */
.cb-sec{display:flex;align-items:baseline;gap:12px;margin:26px 0 12px}.cb-sec h3{margin:0;font-size:19px;font-weight:800}.cb-sec p{margin:0;color:var(--ink-3);font-size:13px}
.cb-sec::after{content:"";flex:1;height:1px;background:linear-gradient(90deg,var(--line-2),transparent)}
.cb-card{background:linear-gradient(180deg,var(--card),#101828);border:1px solid var(--line);border-radius:var(--r);padding:18px;transition:border-color var(--t),transform var(--t);animation:fadeUp .5s both}
.cb-card:hover{border-color:var(--line-2)}
.cb-grid{display:grid;gap:14px}.g2{grid-template-columns:repeat(2,1fr)}.g3{grid-template-columns:repeat(3,1fr)}.g4{grid-template-columns:repeat(4,1fr)}.g5{grid-template-columns:repeat(5,1fr)}.g6{grid-template-columns:repeat(6,1fr)}
@media(max-width:1000px){.g3,.g4,.g5,.g6{grid-template-columns:repeat(2,1fr)}}@media(max-width:640px){.g2,.g3,.g4,.g5,.g6{grid-template-columns:1fr}}
.cb-kpi{position:relative;overflow:hidden;padding:16px 18px;border-radius:var(--r);border:1px solid var(--line);background:linear-gradient(160deg,var(--card-2),var(--card));animation:fadeUp .55s both}
.cb-kpi::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--k,var(--accent))}
.cb-kpi i{display:block;font-style:normal;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);font-weight:700}
.cb-kpi b{display:block;font-size:30px;font-weight:800;margin:4px 0 2px;color:var(--ink);letter-spacing:-.02em}
.cb-kpi span{font-size:12px;color:var(--ink-2)}
.cb-pill{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;border:1px solid var(--line-2);background:var(--card-2);color:var(--ink-2);font-size:11.5px;font-weight:700}
.cb-pill.teal{color:#5EEAD4;border-color:rgba(20,184,166,.5);background:rgba(20,184,166,.12)}.cb-pill.gold{color:#FCD34D;border-color:rgba(232,163,61,.5);background:rgba(232,163,61,.12)}
.cb-pill.red{color:#FCA5A5;border-color:rgba(240,97,109,.5);background:rgba(240,97,109,.12)}.cb-pill.mag{color:#F5D0FE;border-color:rgba(232,121,249,.45);background:rgba(232,121,249,.1)}
.cb-live{display:inline-flex;align-items:center;gap:7px;font-size:11px;font-weight:800;letter-spacing:.12em;color:#FCA5A5}
.cb-live::before{content:"";width:8px;height:8px;border-radius:50%;background:var(--bad);box-shadow:0 0 0 0 rgba(240,97,109,.7);animation:pulse 1.6s infinite}
.cb-callout{border:1px solid var(--line-2);border-left:3px solid var(--accent);background:rgba(20,184,166,.07);border-radius:var(--r-sm);padding:12px 16px;color:var(--ink-2);font-size:13.5px;margin:8px 0 14px}
.cb-callout.warn{border-left-color:var(--gold);background:rgba(232,163,61,.07)}.cb-callout b{color:var(--ink)}
/* match card */
.cb-match{padding:16px 18px;border-radius:var(--r);border:1px solid var(--line);background:linear-gradient(160deg,#16233B,#101828);animation:fadeUp .5s both;transition:transform var(--t),border-color var(--t)}
.cb-match:hover{transform:translateY(-3px);border-color:var(--accent)}
.cb-mh{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:12px;font-size:11.5px;color:var(--ink-3);font-weight:700;letter-spacing:.04em}
.cb-row{display:flex;align-items:center;gap:12px;padding:6px 0}.cb-row .nm{font-weight:700;font-size:15px;flex:1}.cb-score{font-weight:800;font-size:19px}.cb-score small{display:block;font-size:11px;color:var(--ink-3);font-weight:600;text-align:right}
.cb-crest{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;font-size:12px;font-weight:800;color:#fff;letter-spacing:.02em;box-shadow:inset 0 0 0 1px rgba(255,255,255,.18),0 6px 14px rgba(0,0,0,.35);flex:none}
.cb-status{margin-top:10px;padding-top:10px;border-top:1px dashed var(--line-2);font-size:12.5px;color:var(--gold);font-weight:600}
.cb-venue{font-size:11.5px;color:var(--ink-3);margin-top:4px}
/* form pills */
.cb-form{display:inline-flex;gap:4px}.cb-form i{width:20px;height:20px;border-radius:6px;display:grid;place-items:center;font-style:normal;font-size:10.5px;font-weight:800;color:#06241F}
.cb-form i.W{background:var(--good)}.cb-form i.L{background:var(--bad);color:#2A0A0D}
/* player card */
.cb-pcard{position:relative;overflow:hidden;border-radius:22px 22px 30px 30px;padding:16px 16px 14px;color:#0B1220;min-height:300px;animation:fadeUp .6s both;transition:transform var(--t) , box-shadow var(--t);box-shadow:0 14px 30px rgba(0,0,0,.4)}
.cb-pcard:hover{transform:translateY(-6px) rotate(-.4deg);box-shadow:0 22px 44px rgba(0,0,0,.5)}
.cb-pcard.gold{background:linear-gradient(155deg,#F8E1A1,#E8A33D 55%,#8B5A12)}.cb-pcard.silver{background:linear-gradient(155deg,#E2E8F0,#94A3B8 55%,#475569)}.cb-pcard.teal{background:linear-gradient(155deg,#99F6E4,#14B8A6 55%,#0B5D56)}
.cb-pcard::before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 80% 8%,rgba(255,255,255,.55),transparent 45%),repeating-linear-gradient(115deg,rgba(255,255,255,.07) 0 6px,transparent 6px 14px)}
.cb-pcard>*{position:relative}
.cb-ovr{font-size:46px;font-weight:800;line-height:.95;letter-spacing:-.04em}.cb-prole{font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;opacity:.75}
.cb-av{width:84px;height:84px;margin:6px auto 8px;border-radius:50%;display:grid;place-items:center;font-size:30px;font-weight:800;background:rgba(11,18,32,.82);color:#fff;box-shadow:0 0 0 4px rgba(255,255,255,.35)}
.cb-pn{text-align:center;font-weight:800;font-size:16px;letter-spacing:-.01em;border-bottom:1px solid rgba(11,18,32,.25);padding-bottom:6px;margin-bottom:8px}
.cb-ps{display:grid;grid-template-columns:repeat(3,1fr);text-align:center;gap:4px}.cb-ps b{display:block;font-size:20px;font-weight:800}.cb-ps span{font-size:10px;font-weight:800;letter-spacing:.1em;opacity:.7}
.cb-pf{text-align:center;margin-top:8px;font-size:11px;font-weight:700;opacity:.8}
/* podium */
.cb-podium{display:flex;align-items:flex-end;justify-content:center;gap:12px;margin:8px 0 14px}
.cb-pod{flex:1;max-width:240px;text-align:center;border-radius:16px 16px 0 0;padding:14px 10px 12px;border:1px solid var(--line-2);border-bottom:0;background:linear-gradient(180deg,var(--card-2),var(--card));animation:rise .7s both}
.cb-pod .rk{font-size:12px;font-weight:800;letter-spacing:.14em;color:var(--ink-3)}.cb-pod .nm{font-weight:800;font-size:15px;margin:6px 0 2px}.cb-pod .vl{font-size:30px;font-weight:800;letter-spacing:-.03em}.cb-pod .sb{font-size:12px;color:var(--ink-3)}
.cb-pod.p1{min-height:190px;border-top:3px solid var(--gold)}.cb-pod.p1 .vl{color:var(--gold)}.cb-pod.p2{min-height:156px;border-top:3px solid #CBD5E1}.cb-pod.p3{min-height:130px;border-top:3px solid #C28336}
/* rows / leaderboard bars */
.cb-lb{display:flex;align-items:center;gap:12px;padding:9px 12px;border-radius:12px;border:1px solid transparent;transition:background var(--t)}
.cb-lb:hover{background:var(--card-2);border-color:var(--line)}.cb-lb .n{width:22px;color:var(--ink-3);font-weight:800;font-size:12px}.cb-lb .nm{flex:1;font-weight:700;font-size:14px}.cb-lb .nm small{display:block;color:var(--ink-3);font-weight:500;font-size:11.5px}
.cb-bar{flex:1.2;height:7px;border-radius:99px;background:var(--line);overflow:hidden}.cb-bar>div{height:100%;border-radius:99px;background:linear-gradient(90deg,var(--accent-dim),var(--gold))}.cb-lb .v{width:70px;text-align:right;font-weight:800}
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes rise{from{opacity:0;transform:translateY(40px)}to{opacity:1;transform:none}}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(240,97,109,.7)}70%{box-shadow:0 0 0 10px rgba(240,97,109,0)}100%{box-shadow:0 0 0 0 rgba(240,97,109,0)}}
@keyframes marquee{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@keyframes spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){[class^="cb-"],[class*=" cb-"],[class^="cb-"]::before,[class*=" cb-"]::before,[class^="cb-"]::after,[class*=" cb-"]::after,.cb-brand svg{animation-duration:1ms!important;animation-iteration-count:1!important;transition-duration:1ms!important}}
"""

BALL_SVG = (
    '<svg viewBox="0 0 40 40" aria-hidden="true"><defs><radialGradient id="cbg" cx="35%" cy="30%" r="80%">'
    '<stop offset="0" stop-color="#FB7185"/><stop offset="1" stop-color="#9F1239"/></radialGradient></defs>'
    '<circle cx="20" cy="20" r="18" fill="url(#cbg)"/><path d="M6 12c8 5 8 11 0 16M34 12c-8 5-8 11 0 16" '
    'stroke="#FDE68A" stroke-width="1.4" fill="none" stroke-dasharray="2.2 2"/></svg>'
)

CREST = {
    "IND": ("#1D4ED8", "#38BDF8"),
    "AUS": ("#B45309", "#FBBF24"),
    "ENG": ("#BE123C", "#1E3A8A"),
    "SA": ("#15803D", "#FBBF24"),
    "NZ": ("#0F172A", "#475569"),
    "PAK": ("#166534", "#22C55E"),
    "SL": ("#1E40AF", "#F59E0B"),
    "AFG": ("#1D4ED8", "#DC2626"),
    "WI": ("#7F1D1D", "#EAB308"),
    "BAN": ("#047857", "#DC2626"),
}


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def compact(markup: str) -> str:
    """Strip indentation/newlines so Streamlit's Markdown never treats the HTML as a code block."""
    return "".join(line.strip() for line in markup.strip().splitlines())


def render(markup: str) -> None:
    st.markdown(compact(markup), unsafe_allow_html=True)


def inject_theme() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def _crest_colors(short: str) -> tuple[str, str]:
    if short in CREST:
        return CREST[short]
    h = zlib.crc32(short.encode()) % 360
    return f"hsl({h},65%,38%)", f"hsl({(h + 40) % 360},70%,50%)"


def crest(short: str) -> str:
    a, b = _crest_colors(short)
    return f'<div class="cb-crest" style="background:linear-gradient(135deg,{a},{b})">{esc(short[:3])}</div>'


def hero(kicker: str, title: str, subtitle: str, pills: Iterable[tuple[str, str]] = ()) -> None:
    chips = "".join(f'<span class="cb-pill {k}">{esc(t)}</span> ' for t, k in pills)
    render(
        f'<section class="cb-hero"><div class="cb-kicker">{esc(kicker)}</div><h2>{esc(title)}</h2><p>{esc(subtitle)}</p>{chips}</section>'
    )


def section(title: str, sub: str = "") -> None:
    render(f'<div class="cb-sec"><h3>{esc(title)}</h3><p>{esc(sub)}</p></div>')


def callout(text: str, kind: str = "info") -> None:
    render(f'<div class="cb-callout {"warn" if kind == "warn" else ""}">{text}</div>')


def kpi_row(items: list[tuple[str, str, str, str]], cols: int = 4) -> None:
    """items: (label, value, caption, colour)"""
    cells = "".join(
        f'<div class="cb-kpi" style="--k:{c};animation-delay:{i * 70}ms"><i>{esc(l)}</i><b>{esc(v)}</b><span>{esc(s)}</span></div>'
        for i, (l, v, s, c) in enumerate(items)
    )
    render(f'<div class="cb-grid g{cols}">{cells}</div>')


def hud(stats: list[tuple[str, str, str]], chips: list[tuple[str, str]]) -> None:
    st_html = "".join(
        f'<div class="cb-stat {c}"><b>{esc(v)}</b><i>{esc(l)}</i></div>' for l, v, c in stats
    )
    ch = "".join(f'<span class="cb-pill {k}">{esc(t)}</span>' for t, k in chips)
    render(
        f'<div class="cb-hud"><div class="cb-brand">{BALL_SVG}<div><h1>Cricbuzz LiveStats</h1><span>Real-time insights &middot; SQL analytics</span></div></div>{st_html}{ch}</div>'
    )


def ticker(items: list[str]) -> None:
    if not items:
        return
    seg = "".join(f'<span class="cb-tick">{i}</span>' for i in items)
    render(
        f'<div class="cb-ticker" role="marquee" aria-label="Match ticker"><div class="cb-track">{seg}{seg}</div></div>'
    )


def _score_html(score: dict) -> str:
    if not score.get("innings"):
        return '<div class="cb-score" style="color:var(--ink-3);font-size:13px">Yet to bat</div>'
    last = score["innings"][-1]
    prior = " &amp; ".join(
        f"{i['runs']}/{i['wkts']}" if i["wkts"] != 10 else str(i["runs"])
        for i in score["innings"][:-1]
    )
    cur = f"{last['runs']}/{last['wkts']}" if last["wkts"] != 10 else str(last["runs"])
    sub = f"{esc(prior)} &amp; " if prior else ""
    return f'<div class="cb-score">{sub}{cur}<small>({esc(last["overs"])} ov)</small></div>'


def match_card(m: dict, delay: int = 0) -> str:
    live = (
        '<span class="cb-live">LIVE</span>'
        if m.get("is_live")
        else f'<span class="cb-pill">{esc(m.get("state") or "Match")}</span>'
    )
    rows = ""
    for t, s, k in (
        (m["team1"], m["team1_short"], "score1"),
        (m["team2"], m["team2_short"], "score2"),
    ):
        rows += (
            f'<div class="cb-row">{crest(s)}<div class="nm">{esc(t)}</div>{_score_html(m[k])}</div>'
        )
    venue = ", ".join(x for x in (m.get("venue"), m.get("city")) if x)
    return compact(
        f'<div class="cb-match" style="animation-delay:{delay}ms"><div class="cb-mh"><span>{esc(m.get("format"))} &middot; {esc(m.get("desc"))}</span>{live}</div>'
        f'{rows}<div class="cb-status">{esc(m.get("status"))}</div><div class="cb-venue">{esc(venue)}</div></div>'
    )


def form_pills(results: list[str]) -> str:
    return (
        '<span class="cb-form">' + "".join(f"<i class='{r}'>{r}</i>" for r in results) + "</span>"
    )


def player_card(r: dict, delay: int = 0) -> str:
    tier = "gold" if r["OVR"] >= 88 else ("silver" if r["OVR"] >= 76 else "teal")
    initials = "".join(w[0] for w in str(r["full_name"]).split()[:2]).upper()
    role = {"Batsman": "BAT", "Bowler": "BOWL", "All-rounder": "AR", "Wicket-keeper": "WK"}.get(
        r["playing_role"], ""
    )
    return compact(
        f'<div class="cb-pcard {tier}" style="animation-delay:{delay}ms"><div style="display:flex;justify-content:space-between">'
        f'<div><div class="cb-ovr">{int(r["OVR"])}</div><div class="cb-prole">{role}</div></div>'
        f'<div class="cb-prole" style="text-align:right;max-width:110px">{esc(r["country"])}</div></div>'
        f'<div class="cb-av">{esc(initials)}</div><div class="cb-pn">{esc(r["full_name"])}</div>'
        f'<div class="cb-ps"><div><b>{int(r["BAT"])}</b><span>BAT</span></div><div><b>{int(r["BWL"])}</b><span>BWL</span></div>'
        f"<div><b>{int(r['FLD'])}</b><span>FLD</span></div></div>"
        f'<div class="cb-pf">{int(r["runs"]):,} runs &middot; {int(r["wickets"])} wkts</div></div>'
    )


def podium(rows: list[tuple[str, str, str]]) -> None:
    """rows: [(name, value, sub)] top-3 in rank order."""
    if len(rows) < 3:
        return
    order = [(1, rows[1], "p2"), (0, rows[0], "p1"), (2, rows[2], "p3")]
    cells = "".join(
        f'<div class="cb-pod {c}" style="animation-delay:{i * 120}ms"><div class="rk">#{idx + 1}</div>'
        f'<div class="nm">{esc(r[0])}</div><div class="vl">{esc(r[1])}</div><div class="sb">{esc(r[2])}</div></div>'
        for i, (idx, r, c) in enumerate(order)
    )
    render(f'<div class="cb-podium">{cells}</div>')


def leaderboard(rows: list[tuple[str, str, float, str]], start: int = 1) -> None:
    """rows: [(name, subtitle, ratio 0-1, value_text)]"""
    html_rows = "".join(
        f'<div class="cb-lb"><span class="n">{i + start}</span><div class="nm">{esc(n)}<small>{esc(s)}</small></div>'
        f'<div class="cb-bar"><div style="width:{max(2, min(100, ratio * 100)):.0f}%"></div></div><span class="v tnum">{esc(v)}</span></div>'
        for i, (n, s, ratio, v) in enumerate(rows)
    )
    render(f'<div class="cb-card" style="padding:8px">{html_rows}</div>')



def style_fig(fig, height: int = 380, legend: bool = True):
    """Apply the dark premium Plotly look."""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=COLORWAY,
        font=dict(
            family="Inter, sans-serif",
            color=TOKENS["ink2"],
            size=12,
        ),
        margin=dict(l=45, r=20, t=100, b=45),
        title=dict(
            font=dict(size=14, color=TOKENS["ink"]),
            x=0.01,
        ),
        showlegend=legend,
        legend=dict(
            orientation="h",
            y=1.02,
            x=0,
            xanchor="left",
            yanchor="bottom",
            bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="closest",
        hoverlabel=dict(
            bgcolor="#182238",
            bordercolor=TOKENS["accent"],
            font=dict(family="Inter, Arial, sans-serif", size=13, color=TOKENS["ink"]),
            align="left",
            namelength=-1,
        ),
    )

    fig.update_xaxes(
        gridcolor=TOKENS["line"],
        zerolinecolor=TOKENS["line"],
        linecolor=TOKENS["line"],
    )
    fig.update_yaxes(
        gridcolor=TOKENS["line"],
        zerolinecolor=TOKENS["line"],
        linecolor=TOKENS["line"],
    )

    return fig