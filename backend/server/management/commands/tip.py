"""Module for 'tip' command that updates predictions for upcoming AFL matches."""

from django.core.management.base import BaseCommand
from redis import Redis
from rq import Queue, Worker

from server.tipping import Tipper


TWENTY_MINS = 1200
QUEUE_TIMEOUT = TWENTY_MINS


def _update_match_data():
    Tipper().update_match_data()


def _update_match_predictions():
    Tipper().update_match_predictions()


def _submit_tips():
    Tipper().submit_tips()


class Command(BaseCommand):
    """manage.py command for 'tip' that updates predictions for upcoming AFL matches."""

    help = """
    Check if there are upcoming AFL matches and make predictions on results
    for all unplayed matches in the upcoming/current round.
    """

    def handle(self, *_args, verbose=1, **_kwargs) -> None:  # pylint: disable=W0221
        """
        Run 'tip' command for end-to-end tipping process.

        This includes:
        1. Updating data for upcoming matches & backfilling past match data.
        2. Updating or creating predictions for upcoming matches.
        3. Submitting tips to competition websites
            (footytips.com.au & Monash by default).
        """
        redis_conn = Redis(host="redis", port=6379)
        queue = Queue(connection=redis_conn)

        queue.enqueue(_update_match_data, job_id="match", job_timeout=QUEUE_TIMEOUT)
        queue.enqueue(
            _update_match_predictions,
            job_id="prediction",
            depends_on="match",
            job_timeout=QUEUE_TIMEOUT,
        )
        queue.enqueue(
            _submit_tips,
            job_id="submit",
            depends_on="prediction",
            job_timeout=QUEUE_TIMEOUT,
        )

        worker = Worker([queue], connection=redis_conn)
        worker.work()
