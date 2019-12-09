from copy import copy
from unittest.mock import patch, call

from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from django.db.utils import DataError
from django.core.exceptions import ValidationError

from server.models import Match, Team
from server.tests.fixtures.data_factories import (
    fake_fixture_data,
    fake_match_results_data,
)
from server.tests.fixtures.factories import FullMatchFactory


ONE_YEAR_RANGE = (2014, 2015)


class TestMatch(TestCase):
    def setUp(self):
        match_datetime = timezone.make_aware(datetime(2018, 5, 5))
        self.match = Match.objects.create(
            start_date_time=match_datetime, round_number=5, venue="Corporate Stadium"
        )
        self.home_team = Team.objects.create(name="Richmond")
        self.away_team = Team.objects.create(name="Melbourne")

        self.match.teammatch_set.create(
            team=self.home_team, match=self.match, at_home=True, score=50
        )
        self.match.teammatch_set.create(
            team=self.away_team, match=self.match, at_home=False, score=100
        )

    def test_get_or_create_from_raw_data(self):
        fixture_data = fake_fixture_data(1, ONE_YEAR_RANGE).to_dict("records")[0]
        match_count = Match.objects.count()

        with self.subTest("with validation error"):
            invalid_fixture_data = copy(fixture_data)
            invalid_fixture_data["venue"] = "venue" * 25

            with self.assertRaises(DataError):
                Match.get_or_create_from_raw_data(invalid_fixture_data)

            self.assertEqual(Match.objects.count(), match_count)

        created_match = Match.get_or_create_from_raw_data(fixture_data)

        self.assertIsInstance(created_match, Match)
        self.assertEqual(Match.objects.count(), match_count + 1)

        with self.subTest("with existing match record"):
            gotten_match = Match.get_or_create_from_raw_data(fixture_data)

            self.assertEqual(gotten_match, created_match)
            self.assertEqual(Match.objects.count(), match_count + 1)

    def test_played_without_results(self):
        FullMatchFactory(
            start_date_time=timezone.localtime() - timedelta(days=1),
            home_team_match__score=0,
            away_team_match__score=0,
        )
        FullMatchFactory(
            start_date_time=timezone.localtime() - timedelta(days=1),
            home_team_match__score=50,
            away_team_match__score=80,
        )
        FullMatchFactory(
            start_date_time=timezone.localtime() + timedelta(days=1),
            home_team_match__score=0,
            away_team_match__score=0,
        )

        played_matches_without_results = Match.played_without_results()

        self.assertEqual(played_matches_without_results.count(), 1)

    def test_earliest_data_without_results(self):
        FullMatchFactory(
            start_date_time=timezone.localtime() - timedelta(days=1),
            home_team_match__score=50,
            away_team_match__score=80,
        )
        FullMatchFactory(
            start_date_time=timezone.localtime() + timedelta(days=1),
            home_team_match__score=0,
            away_team_match__score=0,
        )

        with self.subTest("when all matches have results or haven't been played"):
            earliest_date_without_results = Match.earliest_date_without_results()

            self.assertIsNone(earliest_date_without_results)

        played_resultless = FullMatchFactory(
            start_date_time=timezone.localtime() - timedelta(days=1),
            home_team_match__score=0,
            away_team_match__score=0,
        )

        earliest_date_without_results = Match.earliest_date_without_results()

        self.assertEqual(
            played_resultless.start_date_time, earliest_date_without_results
        )

    @patch("server.models.match.Match.update_result")
    def test_update_results(self, mock_update_result):
        match_results = fake_match_results_data(3, ONE_YEAR_RANGE)
        calls = []

        for _idx, match_result in match_results.iterrows():
            FullMatchFactory(
                home_team_match__score=0,
                away_team_match__score=0,
                start_date_time=match_result["date"],
                round_number=match_result["round_number"],
                home_team_match__team__name=match_result["home_team"],
                away_team_match__team__name=match_result["away_team"],
            )
            calls.append(call(match_result))

        Match.update_results(match_results)

        self.assertEqual(mock_update_result.call_count, 3)

    def test_update_result(self):
        match_results = fake_match_results_data(1, ONE_YEAR_RANGE)
        match_result = match_results.iloc[0, :]

        match = FullMatchFactory(
            home_team_match__score=0,
            away_team_match__score=0,
            start_date_time=match_result["date"],
            round_number=match_result["round_number"],
            home_team_match__team__name=match_result["home_team"],
            away_team_match__team__name=match_result["away_team"],
        )
        winner_name = (
            match_result["home_team"]
            if match_result["home_score"] > match_result["away_score"]
            else match_result["away_team"]
        )

        winner = Team.objects.get(name=winner_name)
        match.prediction_set.update(predicted_winner=winner)
        match.update_result(match_results)

        match_scores = set(match.teammatch_set.values_list("score", flat=True))
        match_data_scores = set(match_result[["home_score", "away_score"]])
        self.assertEqual(match_scores, match_data_scores)
        self.assertGreaterEqual(match.prediction_set.filter(is_correct=True).count(), 1)

    def test_year(self):
        self.assertEqual(self.match.year, 2018)

    def test_winner(self):
        self.assertEqual(self.match.winner, self.away_team)

    def test_is_draw(self):
        self.assertFalse(self.match.is_draw)

        self.match.teammatch_set.update(score=100)
        self.assertTrue(self.match.is_draw)

    def test_has_been_played(self):
        self.assertTrue(self.match.has_been_played)

        with self.subTest("when there's no score"):
            self.match.teammatch_set.update(score=0)

            self.assertTrue(self.match.has_been_played)

        with self.subTest("when the match hasn't finished yet"):
            team_match = self.match.teammatch_set.first()
            team_match.score = 100
            team_match.save()

            self.match.start_date_time = timezone.localtime() - timedelta(hours=1)
            self.match.save()

            self.assertFalse(self.match.has_been_played)

    def test_has_results(self):
        self.assertTrue(self.match.has_results)

        with self.subTest("when there's no score"):
            self.match.teammatch_set.update(score=0)

            self.assertFalse(self.match.has_results)

        with self.subTest("when the match hasn't finished yet"):
            team_match = self.match.teammatch_set.first()
            team_match.score = 100
            team_match.save()

            self.match.start_date_time = timezone.localtime() - timedelta(hours=1)
            self.match.save()

            self.assertFalse(self.match.has_results)

    def test_validations(self):
        self.match.full_clean()

        with self.subTest("with duplicate start_date_time/venue combination"):
            invalid_match = Match(
                start_date_time=self.match.start_date_time,
                venue=self.match.venue,
                round_number=2,
            )

            with self.assertRaises(ValidationError, msg="duplicate"):
                invalid_match.full_clean()

        with self.subTest("with a timezone-unaware start_date_time"):
            invalid_start_date_time = datetime.now()
            invalid_match = Match(
                start_date_time=invalid_start_date_time,
                venue="Some Venue",
                round_number=5,
            )

            with self.assertRaises(
                ValidationError, msg=f"{invalid_start_date_time} is not set to the UTC"
            ):
                invalid_match.full_clean()
