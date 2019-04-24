"""Module for data cleaning functions"""

from typing import Optional, Pattern, Callable, List
from datetime import datetime, date
import re
import pandas as pd

from machine_learning.data_config import TEAM_TRANSLATIONS, FOOTYWIRE_VENUE_TRANSLATIONS
from project.settings.common import MELBOURNE_TIMEZONE

MATCH_COL_TRANSLATIONS = {
    "home_points": "home_score",
    "away_points": "away_score",
    "margin": "home_margin",
    "season": "year",
    "game": "match_id",
    "home_goals": "home_team_goals",
    "away_goals": "away_team_goals",
    "home_behinds": "home_team_behinds",
    "away_behinds": "away_team_behinds",
}
PLAYER_COL_TRANSLATIONS = {
    "time_on_ground__": "time_on_ground",
    "id": "player_id",
    "round": "round_number",
    "season": "year",
}
REGULAR_ROUND: Pattern = re.compile(r"round\s+(\d+)$", flags=re.I)

UNUSED_PLAYER_COLS = [
    "local_start_time",
    "attendance",
    "hq1g",
    "hq1b",
    "hq2g",
    "hq2b",
    "hq3g",
    "hq3b",
    "hq4g",
    "hq4b",
    "aq1g",
    "aq1b",
    "aq2g",
    "aq2b",
    "aq3g",
    "aq3b",
    "aq4g",
    "aq4b",
    "jumper_no_",
    "umpire_1",
    "umpire_2",
    "umpire_3",
    "umpire_4",
    "substitute",
    "group_id",
]

PLAYER_FILLNA = {
    "first_name": "",
    "surname": "",
    "player_id": 0,
    "playing_for": "",
    "kicks": 0,
    "marks": 0,
    "handballs": 0,
    "goals": 0,
    "behinds": 0,
    "hit_outs": 0,
    "tackles": 0,
    "rebounds": 0,
    "inside_50s": 0,
    "clearances": 0,
    "clangers": 0,
    "frees_for": 0,
    "frees_against": 0,
    "brownlow_votes": 0,
    "contested_possessions": 0,
    "uncontested_possessions": 0,
    "contested_marks": 0,
    "marks_inside_50": 0,
    "one_percenters": 0,
    "bounces": 0,
    "goal_assists": 0,
    "time_on_ground": 0,
    "player_name": "",
}

LABEL_COLS = ["score", "oppo_score"]


def _map_betting_teams_to_match_teams(team_name: str) -> str:
    if team_name in TEAM_TRANSLATIONS.keys():
        return TEAM_TRANSLATIONS[team_name]

    return team_name


def clean_betting_data(betting_data: pd.DataFrame) -> pd.DataFrame:
    return (
        betting_data.rename(columns={"season": "year", "round": "round_number"})
        .drop(
            [
                "home_win_paid",
                "home_line_paid",
                "away_win_paid",
                "away_line_paid",
                "venue",
                "round_label",
                "home_margin",
                "away_margin",
            ],
            axis=1,
        )
        .assign(
            home_team=lambda df: df["home_team"].map(_map_betting_teams_to_match_teams),
            away_team=lambda df: df["away_team"].map(_map_betting_teams_to_match_teams),
            date=lambda df: df["date"].dt.tz_localize(MELBOURNE_TIMEZONE),
        )
    )


def _map_footywire_venues(venue: str) -> str:
    if venue not in FOOTYWIRE_VENUE_TRANSLATIONS.keys():
        return venue

    return FOOTYWIRE_VENUE_TRANSLATIONS[venue]


def _round_type_column(data_frame: pd.DataFrame) -> pd.DataFrame:
    return data_frame["round_label"].map(
        lambda label: "Finals" if re.search(REGULAR_ROUND, label) is None else "Regular"
    )


def _match_data_from_next_round(future_match_data):
    right_now = datetime.now(tz=MELBOURNE_TIMEZONE)  # pylint: disable=W0612
    next_round = future_match_data.query("date > @right_now")["round"].min()

    return (
        future_match_data.assign(round_type=_round_type_column)
        .loc[
            future_match_data["round"] == next_round,
            [
                "date",
                "venue",
                "season",
                "round",
                "home_team",
                "away_team",
                "round_type",
            ],
        ]
        .rename(columns={"round": "round_number", "season": "year"})
        .assign(venue=lambda df: df["venue"].map(_map_footywire_venues))
    )


def _append_fixture_to_match_data(
    match_data: pd.DataFrame, fixture_data: pd.DataFrame
) -> pd.DataFrame:
    if fixture_data is None:
        return match_data

    return (
        pd.concat([match_data, _match_data_from_next_round(fixture_data)], sort=False)
        .reset_index(drop=True)
        .drop_duplicates(
            subset=["date", "venue", "year", "round_number", "home_team", "away_team"]
        )
        .fillna(0)
    )


# fitzRoy returns integers that represent some sort of datetime, and the only
# way to parse them is converting them to dates.
# NOTE: If the matches parsed only go back to 1990 (give or take, I can't remember)
# you can parse the date integers into datetime
def _parse_fitzroy_dates(data_frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(data_frame["date"], unit="D").dt.tz_localize(
        MELBOURNE_TIMEZONE
    )


# ID values are converted to floats automatically, making for awkward strings later.
# We want them as strings, because sometimes we have to use player names as replacement
# IDs, and we concatenate multiple ID values to create a unique index.
def _convert_id_to_string(id_label: str) -> Callable:
    return lambda df: df[id_label].astype(int).astype(str)


def _filter_out_dodgy_data(duplicate_subset=None) -> Callable:
    return lambda df: (
        df.sort_values("date", ascending=True)
        # Some early matches (1800s) have fully-duplicated rows.
        # Also, drawn finals get replayed, which screws up my indexing and a bunch of other
        # data munging, so getting match_ids for the repeat matches, and filtering
        # them out of the data frame
        .drop_duplicates(subset=duplicate_subset, keep="last")
        # There were some weird round-robin rounds in the early days, and it's easier to
        # drop them rather than figure out how to split up the rounds.
        .query(
            "(year != 1897 | round_number != 15) "
            "& (year != 1924 | round_number != 19)"
        )
    )


def clean_match_data(
    past_match_data: pd.DataFrame, fixture_data: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    match_data = (
        past_match_data.rename(columns=MATCH_COL_TRANSLATIONS)
        .assign(
            date=_parse_fitzroy_dates, away_margin=lambda df: df["home_margin"] * -1
        )
        .astype({"year": int, "round_number": int})
        .pipe(
            _filter_out_dodgy_data(
                duplicate_subset=["year", "round_number", "home_team", "away_team"]
            )
        )
        .assign(match_id=_convert_id_to_string("match_id"))
        .drop(["round"], axis=1)
    )

    return _append_fixture_to_match_data(match_data, fixture_data)


def _player_id_col(data_frame: pd.DataFrame) -> pd.DataFrame:
    # Need to add year to ID, because there are some
    # player_id/match_id combos, decades apart, that by chance overlap
    return (
        data_frame["year"].astype(str)
        + "."
        + data_frame["match_id"].astype(str)
        + "."
        + data_frame["player_id"].astype(str)
    )


def _clean_roster_data(
    player_data_frame: pd.DataFrame, roster_data: pd.DataFrame
) -> pd.DataFrame:
    if not roster_data.any().any():
        return roster_data.assign(player_id=[])

    year = date.today().year

    roster_data_frame = (
        roster_data.merge(
            player_data_frame[["player_name", "player_id"]],
            on=["player_name"],
            how="left",
        )
        .sort_values("player_id", ascending=False)
        # There are some duplicate player names over the years, so we drop the oldest,
        # hoping that the contemporary player matches the one with the most-recent
        # entry into the AFL. If two players with the same name are playing in the
        # league at the same time, that will likely result in errors
        .drop_duplicates(subset=["player_name"], keep="first")
        .assign(
            year=year, date=lambda df: df["date"].dt.tz_localize(MELBOURNE_TIMEZONE)
        )
    )

    # If a player is new to the league, he won't have a player_id per AFL Tables data,
    # so we make one up just using his name
    roster_data_frame["player_id"].fillna(
        roster_data_frame["player_name"], inplace=True
    )

    return roster_data_frame.assign(id=_player_id_col).set_index("id")


def _append_rosters_to_player_data(
    player_data: pd.DataFrame, roster_data: pd.DataFrame
) -> pd.DataFrame:
    if roster_data is None:
        return player_data

    cleaned_roster_data_frame = _clean_roster_data(player_data, roster_data)

    return pd.concat([player_data, cleaned_roster_data_frame], sort=False).fillna(0)


def clean_player_data(
    player_data: pd.DataFrame,
    match_data: pd.DataFrame,
    roster_data: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    cleaned_player_data = (
        player_data.rename(columns=PLAYER_COL_TRANSLATIONS)
        .astype({"year": int})
        .assign(
            # Some player data venues have trailing spaces
            venue=lambda x: x["venue"].str.strip(),
            player_name=lambda x: x["first_name"] + " " + x["surname"],
            player_id=_convert_id_to_string("player_id"),
            date=_parse_fitzroy_dates,
        )
        .drop(UNUSED_PLAYER_COLS + ["first_name", "surname", "round_number"], axis=1)
        # Player data match IDs are wrong for recent years.
        # The easiest way to add correct ones is to graft on the IDs
        # from match_results. Also, match_results round_numbers integers rather than
        # a mix of ints and strings.
        .merge(
            match_data.pipe(clean_match_data).loc[
                :, ["date", "venue", "round_number", "match_id"]
            ],
            on=["date", "venue"],
            how="left",
        )
        .pipe(
            _filter_out_dodgy_data(
                duplicate_subset=["year", "round_number", "player_id"]
            )
        )
        .drop("venue", axis=1)
        # brownlow_votes aren't known until the end of the season
        .fillna({"brownlow_votes": 0})
        # As of 11-10-2018, match_results is still missing finals data from 2018.
        # Joining on date/venue leaves two duplicates played at M.C.G.
        # on 29-4-1986 & 9-8-1986, but that's an acceptable loss of data
        # and easier than munging team names
        .dropna()
        # Need to add year to ID, because there are some
        # player_id/match_id combos, decades apart, that by chance overlap
        .assign(id=_player_id_col)
        .set_index("id")
        .sort_index()
    )

    return _append_rosters_to_player_data(cleaned_player_data, roster_data)


def clean_joined_data(data_frames: List[pd.DataFrame]):
    # We need to sort by length (going from longest to shortest), then keeping first
    # duplicated column to make sure we don't lose earlier values of shared columns
    # (e.g. dropping match data's 'date' column in favor of the betting data 'date'
    # column results in lots of NaT values, because betting data only goes back to 2010)
    sorted_data_frames = sorted(data_frames, key=len, reverse=True)
    joined_data_frame = pd.concat(sorted_data_frames, axis=1)
    duplicate_columns = joined_data_frame.columns.duplicated(keep="first")

    return joined_data_frame.loc[:, ~duplicate_columns]