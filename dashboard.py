import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="Thirty Years of Disco Biscuits Setlists")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go

    return go, mo, pd, px


@app.cell
def _(mo, pd):
    # CSVs live in public/ beside this file so the WebAssembly export bundles them.
    data_dir = mo.notebook_location() / "public"
    shows = pd.read_csv(str(data_dir / "shows.csv"), parse_dates=["date"])
    song_shows = pd.read_csv(str(data_dir / "song_shows.csv"), parse_dates=["date"])
    segue_pairs = pd.read_csv(str(data_dir / "segue_pairs.csv"), parse_dates=["date"])
    return segue_pairs, shows, song_shows


@app.cell
def _(mo, shows, song_shows):
    # Controls. Each is a variable; any cell that reads .value reruns when it changes.
    first_year, last_year = int(shows["year"].min()), int(shows["year"].max())
    years = mo.ui.range_slider(
        start=first_year, stop=last_year, step=1,
        value=[first_year, last_year], label="Years", show_value=True,
    )
    states = mo.ui.multiselect(
        options=sorted(shows["state"].dropna().unique()),
        label="States (empty = all)",
    )
    song_counts = song_shows.groupby("song")["slug"].nunique().sort_values(ascending=False)
    focus_song = mo.ui.dropdown(
        options=["All songs"] + song_counts.index.tolist(),
        value="All songs", label="Focus song", searchable=True,
    )
    top_n = mo.ui.slider(start=5, stop=30, step=5, value=15, label="Top N", show_value=True)
    return focus_song, states, top_n, years


@app.cell
def _(segue_pairs, shows, song_shows, states, years):
    # One filter step feeds all four charts.
    def apply_filters(df):
        mask = df["year"].between(years.value[0], years.value[1])
        if states.value:
            mask &= df["state"].isin(states.value)
        return df[mask]

    f_shows = apply_filters(shows)
    f_songs = apply_filters(song_shows)
    f_pairs = apply_filters(segue_pairs)
    return f_pairs, f_shows, f_songs


@app.cell
def _(f_shows, px):
    # Chart 1: touring calendar. Rows are years, columns are weeks, color is shows that week.
    _weekly = (
        f_shows.assign(week=f_shows["date"].dt.isocalendar().week.astype(int))
        .groupby(["year", "week"]).size().reset_index(name="shows")
    )
    _grid = _weekly.pivot(index="year", columns="week", values="shows").reindex(columns=range(1, 54))
    fig_calendar = px.imshow(
        _grid, aspect="auto", color_continuous_scale="Blues",
        labels={"x": "Week of year", "y": "Year", "color": "Shows"},
        title="When they toured: shows per week",
    )
    fig_calendar.update_yaxes(dtick=1)
    fig_calendar.update_layout(height=420, margin=dict(l=40, r=10, t=50, b=40))
    return (fig_calendar,)


@app.cell
def _(f_songs, focus_song, px, top_n):
    # Chart 2: most-played songs in the filtered shows. The focus song is highlighted.
    _top = (
        f_songs.groupby("song")["slug"].nunique()
        .sort_values(ascending=False).head(top_n.value)
        .rename("shows_played").reset_index()
    )
    _top["focus"] = _top["song"].eq(focus_song.value)
    fig_bar = px.bar(
        _top.iloc[::-1], x="shows_played", y="song", orientation="h",
        color="focus", color_discrete_map={True: "#d95f02", False: "#7f9fc4"},
        labels={"shows_played": "Shows played", "song": ""},
        title=f"Top {top_n.value} songs",
    )
    fig_bar.update_layout(height=420, showlegend=False, margin=dict(l=10, r=10, t=50, b=40))
    return (fig_bar,)


@app.cell
def _(f_songs, focus_song, px):
    # Chart 3: plays per year. One line for the focus song, or the five most played.
    if focus_song.value == "All songs":
        _names = f_songs.groupby("song")["slug"].nunique().nlargest(5).index
    else:
        _names = [focus_song.value]
    _yearly = (
        f_songs[f_songs["song"].isin(_names)]
        .groupby(["year", "song"])["slug"].nunique()
        .rename("shows_played").reset_index()
    )
    fig_line = px.line(
        _yearly, x="year", y="shows_played", color="song", markers=True,
        labels={"year": "Year", "shows_played": "Shows played", "song": ""},
        title="Plays per year",
    )
    fig_line.update_layout(
        height=420, margin=dict(l=40, r=10, t=50, b=40),
        legend=dict(orientation="h", y=-0.2),
    )
    return (fig_line,)


@app.cell
def _(f_pairs, focus_song, go, top_n):
    # Chart 4: segue flow. Left nodes are the song played first, right nodes the song it ran into.
    # Two columns keep A > B > A from forming a loop, which a Sankey cannot draw.
    _pairs = f_pairs
    if focus_song.value != "All songs":
        _pairs = _pairs[(_pairs["source"] == focus_song.value) | (_pairs["target"] == focus_song.value)]
    _links = (
        _pairs.groupby(["source", "target"]).size()
        .sort_values(ascending=False).head(top_n.value * 2)
        .rename("count").reset_index()
    )
    _left = _links["source"].unique().tolist()
    _right = _links["target"].unique().tolist()
    fig_sankey = go.Figure(go.Sankey(
        node=dict(label=_left + _right, pad=12, thickness=14),
        link=dict(
            source=_links["source"].map(_left.index),
            target=_links["target"].map(lambda s: len(_left) + _right.index(s)),
            value=_links["count"],
        ),
    ))
    fig_sankey.update_layout(
        title=f"Segues: song played (left) into next song (right), top {len(_links)} pairs",
        height=420, margin=dict(l=10, r=10, t=50, b=10),
    )
    return (fig_sankey,)


@app.cell
def _(
    f_pairs,
    f_shows,
    fig_bar,
    fig_calendar,
    fig_line,
    fig_sankey,
    focus_song,
    mo,
    states,
    top_n,
    years,
):
    # Layout: controls on top, then a two-by-two grid so every view fits one screen.
    mo.vstack([
        mo.md("# Thirty Years of Disco Biscuits Setlists"),
        mo.hstack([years, states, focus_song, top_n], justify="start", gap=2),
        mo.md(f"**{len(f_shows):,} shows** and **{len(f_pairs):,} segues** in the current selection."),
        mo.hstack([fig_calendar, fig_bar], widths="equal"),
        mo.hstack([fig_line, fig_sankey], widths="equal"),
        mo.md("Data: The Biscuits Internet Project, discobiscuits.net"),
    ])
    return


if __name__ == "__main__":
    app.run()
