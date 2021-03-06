# pylint: disable=missing-docstring,unused-argument

from datetime import date

import numpy as np

from tests.fixtures.factories import MatchFactory, PredictionFactory
from tests.fixtures.data_factories import fake_fixture_data
from tipping.models import Match, Prediction

REASONABLE_NUMBER_OF_RECORDS = 10


def test_creating_valid_match(faunadb_client):
    match = MatchFactory.build()
    # Need to create winner first, so it will have a valid ID when we create match
    match.winner.create()
    saved_match = match.create()

    # It returns the saved match
    assert saved_match == match

    # It saves the match in the DB
    query = "query { findMatchByID(id: %s) { _id } }" % (saved_match.id)
    result = faunadb_client.graphql(query)
    assert result["findMatchByID"]["_id"]


def test_filtering_matches(faunadb_client):  # pylint: disable=unused-argument
    test_seasons = [1942, 1999]
    match_seasons = test_seasons + [date.today().year]
    filter_seasons = test_seasons + [None]

    for n in range(REASONABLE_NUMBER_OF_RECORDS):
        season = (
            match_seasons[n]
            if n < len(match_seasons)
            else int(np.random.choice(match_seasons))
        )
        MatchFactory.create(season=season)

    filter_season = np.random.choice(filter_seasons)
    default_season = date.today().year
    matches = Match.filter_by_season(season=filter_season)

    # It returns at least one match
    assert len(matches) > 0

    # It only returns matches in the given season
    assert all([match.season == filter_season or default_season for match in matches])


def test_getting_or_creating_match_from_raw_data(faunadb_client):
    fixture_data = fake_fixture_data().iloc[0, :]

    created_match = Match.get_or_create_from_raw_data(fixture_data)

    # It saves the match in the DB
    query = "query { findMatchByID(id: %s) { _id } }" % (created_match.id)
    result = faunadb_client.graphql(query)
    assert result["findMatchByID"]["_id"]

    # It gets the same match
    gotten_match = Match.get_or_create_from_raw_data(fixture_data)
    assert created_match.id == gotten_match.id


def test_getting_match_predictions(faunadb_client):
    prediction_count = np.random.randint(1, 5)
    match = MatchFactory.create()
    PredictionFactory.create_batch(prediction_count, match=match)

    predictions = match.predictions

    # It returns predictions
    for prediction in predictions:
        assert isinstance(prediction, Prediction)

    # It returns all predictions associated with the match
    assert len(predictions) == prediction_count
