"""Plotly figure factories (all pass through theme.style_fig for a consistent premium look)."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from utils.theme import COLORWAY, TOKENS, style_fig


def bar_h(
    df: pd.DataFrame, x: str, y: str, title: str = "", color: str | None = None, height: int = 380
):
    d = df.iloc[::-1]
    fig = px.bar(
        d,
        x=x,
        y=y,
        orientation="h",
        color=color,
        title=title,
        color_discrete_sequence=COLORWAY,
        text_auto=".3~s" if d[x].abs().max() > 1000 else ".2f",
    )
    fig.update_traces(marker_line_width=0, textposition="outside", cliponaxis=False)
    fig.update_yaxes(title=None, showgrid=False)
    fig.update_xaxes(title=None)
    return style_fig(fig, height, legend=color is not None)



def column(
    df: pd.DataFrame,
    x: str,
    y: str | list[str],
    title: str = "",
    color: str | None = None,
    barmode: str = "group",
    height: int = 380,
):
    fig = px.bar(
        df,
        x=x,
        y=y,
        color=color,
        barmode=barmode,
        title=title,
        color_discrete_sequence=COLORWAY,
    )
    fig.update_traces(
        marker_line_width=0,
        legendgroup=None,
    )
    fig.for_each_trace(
        lambda trace: trace.update(
            legendgrouptitle_text=None
        )
    )
    fig.update_xaxes(title_text=None)
    fig.update_yaxes(title_text=None)

    show_legend = bool(color) or isinstance(y, list)

    if show_legend:
        fig.update_layout(
            title=dict(
                x=0,
                xanchor="left",
                y=0.98,
                yanchor="top",
                pad=dict(t=8, b=12),
            ),
            legend=dict(
                orientation="h",
                x=0,
                xanchor="left",
                y=1.02,
                yanchor="bottom",
                bgcolor="rgba(0,0,0,0)",
            ),
            margin=dict(t=100, r=20, b=50, l=45),
        )

    return style_fig(fig, height, legend=show_legend)


def donut(labels, values, title: str = "", center: str = "", height: int = 320):
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.68,
            sort=False,
            marker=dict(colors=COLORWAY, line=dict(color=TOKENS["bg"], width=3)),
            textinfo="percent",
            textfont=dict(color="#fff"),
        )
    )
    fig.update_layout(title=title)
    if center:
        fig.add_annotation(
            text=center, showarrow=False, font=dict(size=18, color=TOKENS["ink"], family="Inter")
        )
    return style_fig(fig, height)




def lines(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    title: str = "",
    height: int = 380,
):
    fig = px.line(
        df,
        x=x,
        y=y,
        color=color,
        markers=True,
        title=title,
        color_discrete_sequence=COLORWAY,
    )
    fig.for_each_trace(
        lambda trace: trace.update(
            name=trace.name,
            legendgrouptitle_text=None,
        )
    )
    fig.update_layout(legend_title_text="")

    fig.update_traces(
        line=dict(width=3),
        marker=dict(size=6),
        legendgroup=None,
    )
    fig.for_each_trace(
        lambda trace: trace.update(
            legendgrouptitle_text=None
        )
    )

    fig.update_xaxes(title_text=None)
    fig.update_yaxes(title_text=None)

    if color is not None:
        fig.update_layout(
            title=dict(
                text=title,
                x=0,
                xanchor="left",
                y=1,
                yanchor="top",
            ),
            legend=dict(
                orientation="h",
                x=0,
                xanchor="left",
                y=1.02,
                yanchor="bottom",
                bgcolor="rgba(0,0,0,0)",
            ),
            margin=dict(t=105, r=20, b=40, l=45),
        )
    else:
        fig.update_layout(
            margin=dict(t=55, r=20, b=40, l=45),
        )

    return style_fig(fig, height, legend=color is not None)


def heat(pivot: pd.DataFrame, title: str = "", height: int = 380, fmt: str = ".0f"):
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=[str(c) for c in pivot.columns],
            y=[str(i) for i in pivot.index],
            colorscale=[[0, "#0F1B30"], [0.5, "#0F766E"], [1, "#E8A33D"]],
            texttemplate="%{z:" + fmt + "}",
            xgap=3,
            ygap=3,
            colorbar=dict(thickness=10, outlinewidth=0),
        )
    )
    fig.update_layout(title=title)
    fig.update_yaxes(autorange="reversed", title=None)
    return style_fig(fig, height, legend=False)


def radar(
    categories: list[str], series: dict[str, list[float]], title: str = "", height: int = 420
):
    fig = go.Figure()
    fills = ["rgba(20,184,166,.25)", "rgba(232,163,61,.25)"]
    for i, (name, vals) in enumerate(series.items()):
        fig.add_trace(
            go.Scatterpolar(
                r=vals + vals[:1],
                theta=categories + categories[:1],
                name=name,
                fill="toself",
                line=dict(color=COLORWAY[i], width=3),
                fillcolor=fills[i % 2],
            )
        )
    fig.update_layout(
        title=title,
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                range=[0, 100],
                gridcolor=TOKENS["line"],
                showticklabels=False,
                linecolor=TOKENS["line"],
            ),
            angularaxis=dict(gridcolor=TOKENS["line"], linecolor=TOKENS["line2"]),
        ),
    )
    return style_fig(fig, height)


def innings_bars(df: pd.DataFrame, title: str = "Last innings", height: int = 280):
    colors = [
        TOKENS["gold"] if r >= 100 else (TOKENS["accent"] if r >= 50 else TOKENS["line2"])
        for r in df["runs"]
    ]
    fig = go.Figure(
        go.Bar(
            x=list(range(1, len(df) + 1)),
            y=df["runs"],
            marker_color=colors,
            hovertext=df["match_format"],
        )
    )
    fig.add_trace(
        go.Scatter(
            x=list(range(1, len(df) + 1)),
            y=df["runs"].rolling(5, min_periods=1).mean(),
            mode="lines",
            line=dict(color=TOKENS["magenta"], width=3),
            name="5-inn avg",
        )
    )
    fig.update_layout(title=title)
    fig.update_xaxes(title="Innings (oldest to latest)", tickmode="linear", dtick=1)
    return style_fig(fig, height, legend=False)

def worm(df: pd.DataFrame, height: int = 340):
    """Create a run-progression chart with a clear title and legend."""
    fig = px.line(
        df,
        x="over",
        y="runs",
        color="team",
        color_discrete_sequence=COLORWAY,
    )

    fig.update_traces(line=dict(width=4, shape="spline"))
    fig.update_xaxes(title="Over")
    fig.update_yaxes(title=None)

    style_fig(fig, height, legend=True)

    fig.update_layout(
        title=dict(
            text="Run progression (worm)",
            x=0.02,
            xanchor="left",
            y=0.98,
            yanchor="top",
            pad=dict(t=8, b=12),
        ),
        legend=dict(
            orientation="h",
            x=0.02,
            xanchor="left",
            y=0.88,
            yanchor="top",
            bgcolor="rgba(0,0,0,0)",
        ),
        margin=dict(t=100, r=20, b=40, l=45),
    )

    return fig




def scatter(df: pd.DataFrame, x: str, y: str, label: str, title: str = "", height: int = 400):
    fig = px.scatter(df, x=x, y=y, text=label, title=title, color_discrete_sequence=COLORWAY)
    fig.update_traces(
        marker=dict(size=11, line=dict(width=1, color=TOKENS["bg"])),
        textposition="top center",
        textfont=dict(size=10),
    )
    return style_fig(fig, height, legend=False)


def win_bar(a: str, b: str, pa: float, height: int = 70):
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=[""],
            x=[pa],
            orientation="h",
            marker_color=TOKENS["accent"],
            text=f"{a} {pa:.0f}%",
            textposition="inside",
            insidetextanchor="start",
        )
    )
    fig.add_trace(
        go.Bar(
            y=[""],
            x=[100 - pa],
            orientation="h",
            marker_color=TOKENS["gold"],
            text=f"{b} {100 - pa:.0f}%",
            textposition="inside",
            insidetextanchor="end",
        )
    )
    fig.update_layout(
        barmode="stack",
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False, range=[0, 100]),
        yaxis=dict(visible=False),
    )
    return style_fig(fig, height, legend=False).update_layout(margin=dict(l=0, r=0, t=0, b=0))


def auto_chart(df: pd.DataFrame, hint: dict | None):
    """Return a figure for a query result using the optional hint attached to the question, else None."""
    if df.empty or not hint:
        return None
    kind, x = hint.get("kind"), hint.get("x")
    try:
        if kind == "bar":
            d = df.head(hint.get("limit", 20))
            return (
                bar_h(d, hint["y"], x, color=hint.get("color"))
                if x in d and hint["y"] in d
                else None
            )
        if kind == "pie":
            return donut(df[x], df[hint["y"]], center="")
        if kind == "grouped_bar":
            return column(df, x, hint["y"], barmode="group")
        if kind == "stacked_bar":
            d = df.groupby(hint["facet"]).head(5) if hint.get("facet") else df.copy()
            fig = px.bar(
                d,
                x=x,
                y=hint["y"],
                facet_col=hint.get("facet"),
                barmode="stack",
                color_discrete_sequence=COLORWAY,
            )
            fig.for_each_trace(
                lambda trace: trace.update(
                    legendgrouptitle_text=None,
                )
            )
            fig.update_layout(legend_title_text="")

            fig.for_each_xaxis(lambda a: a.update(title=None, matches=None, showticklabels=True))
            return style_fig(fig, 420)
        if kind == "line":
            top = (
                df.groupby(hint["color"])[hint["y"]]
                .count()
                .sort_values(ascending=False)
                .head(hint.get("max_series", 6))
                .index
            )
            return lines(df[df[hint["color"]].isin(top)], x, hint["y"], hint["color"])
        if kind == "scatter":
            return scatter(df, hint["x"], hint["y"], hint["label"])
    except Exception:  # a chart must never break the page
        return None
    return None