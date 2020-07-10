"""External-facing API for fetching and updating application data."""

from typing import Optional, List, Tuple
from datetime import datetime
from warnings import warn
import pytz

import numpy as np
import pandas as pd

from tipping import data_import, data_export
from tipping.helpers import pivot_team_matches_to_matches
from tipping.types import CleanPredictionData, MatchData, MLModelInfo
from tipping.tipping import MonashSubmitter, FootyTipsSubmitter

DEC = 12
THIRTY_FIRST = 31
JAN = 1
FIRST = 1


def _select_upcoming_matches(
    fixture_data_frame: pd.DataFrame, right_now: datetime
) -> Tuple[Optional[int], Optional[pd.DataFrame]]:
    if not fixture_data_frame.any().any():
        warn(
            "Fixture for the upcoming round haven't been posted yet, "
            "so there's nothing to tip. Try again later."
        )

        return None, None

    latest_match_date = fixture_data_frame["date"].max()

    if right_now > latest_match_date:
        warn(
            f"No matches found after {right_now}. The latest match "
            f"found is at {latest_match_date}\n"
        )

        return None, None

    upcoming_round = int(
        fixture_data_frame.query("date > @right_now").loc[:, "round_number"].min()
    )
    fixture_for_upcoming_round = fixture_data_frame.query(
        "round_number == @upcoming_round"
    )

    return upcoming_round, fixture_for_upcoming_round


def update_fixture_data(verbose=1) -> None:
    """
    Fetch fixture data and send upcoming match data to the main app.

    verbose: How much information to print. 1 prints all messages; 0 prints none.
    """
    right_now = datetime.now(tz=pytz.UTC)
    year = right_now.year

    if verbose == 1:
        print(f"Fetching fixture for {year}...\n")

    fixture_data_frame = data_import.fetch_fixture_data(
        start_date=datetime(year, 1, 1, tzinfo=pytz.UTC),
        end_date=datetime(year, 12, 31, tzinfo=pytz.UTC),
    )

    upcoming_round, upcoming_matches = _select_upcoming_matches(
        fixture_data_frame, right_now
    )

    if upcoming_round is None or upcoming_matches is None:
        return None

    data_export.update_fixture_data(upcoming_matches, upcoming_round)

    return None


def update_match_predictions(tips_submitters=None, verbose=1) -> None:
    """
    Fetch predictions from ML models and send them to the main app.

    verbose: How much information to print. 1 prints all messages; 0 prints none.
    """
    right_now = datetime.now(tz=pytz.UTC)
    end_of_year = datetime(right_now.year, DEC, THIRTY_FIRST, tzinfo=pytz.UTC)
    upcoming_matches = data_import.fetch_fixture_data(right_now, end_of_year)

    if not upcoming_matches.any().any():
        if verbose == 1:
            print("There are no upcoming matches to predict.")
        return None

    next_match = upcoming_matches.sort_values("date").iloc[0, :]
    upcoming_round = int(next_match["round_number"])
    upcoming_season = int(next_match["year"])

    if verbose == 1:
        print(
            "Fetching predictions for round " f"{upcoming_round}, {upcoming_season}..."
        )

    prediction_data = data_import.fetch_prediction_data(
        f"{upcoming_season}-{upcoming_season + 1}", round_number=upcoming_round,
    )

    if verbose == 1:
        print("Predictions received!")

    home_away_df = pivot_team_matches_to_matches(prediction_data)
    match_predictions = home_away_df.replace({np.nan: None}).to_dict("records")

    data_export.update_match_predictions(match_predictions)

    if verbose == 1:
        print("Match predictions sent!")

    if not any(match_predictions):
        if verbose == 1:
            print(
                "No predictions found for the upcoming round. "
                "Not submitting any tips."
            )

        return None

    tips_submitters = tips_submitters or [
        MonashSubmitter(verbose=verbose),
        FootyTipsSubmitter(verbose=verbose),
    ]

    for submitter in tips_submitters:
        submitter.submit_tips(match_predictions)

    return None


def update_match_results(verbose=1) -> None:
    """
    Fetch match results data and send them to the main app.

    verbose: How much information to print. 1 prints all messages; 0 prints none.
    """
    right_now = datetime.now()
    start_of_year = datetime(right_now.year, JAN, FIRST)
    end_of_year = datetime(right_now.year, DEC, THIRTY_FIRST)

    if verbose == 1:
        print(f"Fetching match results for season {right_now.year}")

    match_data = (
        data_import.fetch_match_results_data(
            str(start_of_year), str(end_of_year), fetch_data=True
        )
        .replace({np.nan: None})
        .to_dict("records")
    )

    if verbose == 1:
        print("Match results reveived!")

    data_export.update_match_results(match_data)

    if verbose == 1:
        print("Match results sent!")


def fetch_match_predictions(
    year_range: str,
    round_number: Optional[int] = None,
    ml_models: Optional[List[str]] = None,
    train_models: Optional[bool] = False,
) -> List[CleanPredictionData]:
    """
    Fetch prediction data from ML models.

    Params:
    -------
    year_range: Min (inclusive) and max (exclusive) years for which to fetch data.
        Format is 'yyyy-yyyy'.
    round_number: Specify a particular round for which to fetch data.
    ml_models: List of ML model names to use for making predictions.
    train_models: Whether to train models in between predictions (only applies
        when predicting across multiple seasons).

    Returns:
    --------
        List of prediction data dictionaries.
    """
    prediction_data = data_import.fetch_prediction_data(
        year_range,
        round_number=round_number,
        ml_models=ml_models,
        train_models=train_models,
    )

    home_away_df = pivot_team_matches_to_matches(prediction_data)

    return home_away_df.replace({np.nan: None}).to_dict("records")


def fetch_match_results(
    start_date: str, end_date: str, fetch_data: bool = False
) -> List[MatchData]:
    """
    Fetch results data for past matches.

    Params:
    -------
    start_date: Date-time string that determines the earliest date
        for which to fetch data. Format is 'yyyy-mm-dd'.
    end_date: Date-time string that determines the latest date
        for which to fetch data. Format is 'yyyy-mm-dd'.
    fetch_data: Whether to fetch fresh data. Non-fresh data goes up to end
        of previous season.

    Returns:
    --------
        List of match results data dicts.
    """
    return data_import.fetch_match_results_data(
        start_date, end_date, fetch_data=fetch_data
    ).to_dict("records")


def fetch_ml_models() -> List[MLModelInfo]:
    """
    Fetch general info about all saved ML models.

    Returns:
    --------
    A list of objects with basic info about each ML model.
    """
    return data_import.fetch_ml_model_info().to_dict("records")