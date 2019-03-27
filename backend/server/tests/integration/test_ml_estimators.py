from unittest import skip
from django.test import TestCase

from server.ml_data import JoinedMLData
from server.ml_estimators import BenchmarkEstimator, BaggingEstimator
from server.tests.helpers import regression_accuracy


@skip(
    "These tests are mostly a sanity check for data transformations, but they take way too long, "
    "and the problems caught here would probably be caught while working on data or model changes."
)
class TestMLEstimators(TestCase):
    def setUp(self):
        self.estimators = [
            (
                BenchmarkEstimator(),
                JoinedMLData(train_years=(2010, 2015), test_years=(2016, 2016)),
            ),
            (
                BaggingEstimator(),
                JoinedMLData(train_years=(2010, 2015), test_years=(2016, 2016)),
            ),
        ]

    def test_model_and_data(self):
        for estimator, data in self.estimators:
            test_label = (
                estimator.__class__.__name__ + " and " + data.__class__.__name__
            )

            with self.subTest(test_label):
                X_train, y_train = data.train_data()

                if (
                    "pipeline__correlationselector__labels"
                    in estimator.get_params().keys()
                ):
                    estimator.set_params(pipeline__correlationselector__labels=y_train)

                estimator.fit(X_train, y_train)
                X_test, y_test = data.test_data()
                y_pred = estimator.predict(X_test)

                unique_predictions = set(y_pred)

                # If all the predictions are the same, something went horribly wrong
                self.assertNotEqual(len(unique_predictions), 1)

                accuracy = regression_accuracy(y_test, y_pred)

                # A spot check for leaking data from the match-to-predict
                # (i.e. accidentally including data from 'future' matches in a data row
                # that the model is predicting on).
                # The threshold might change if the models get better, but for now,
                # whenever I see accuracy > 80%, it's always been due to a mistake
                # of this nature.
                self.assertLess(accuracy, 0.8)