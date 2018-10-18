from typing import List, Sequence
import os
import sys
from functools import reduce, partial
import numpy as np
import pandas as pd

PROJECT_PATH: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../')
)

if PROJECT_PATH not in sys.path:
    sys.path.append(PROJECT_PATH)

from server.types import FeatureFunctionType
from server.data_processors.feature_functions import (
    add_last_week_result,
    add_last_week_score,
    add_cum_percent,
    add_cum_win_points,
    add_rolling_pred_win_rate,
    add_rolling_last_week_win_rate,
    add_ladder_position,
    add_win_streak
)

INDEX_COLS: List[str] = ['team', 'year', 'round_number']
REQUIRED_COLS: List[str] = INDEX_COLS + ['oppo_team']

# This is just for convenience based on current needs; might remove it later
DEFAULT_FEATURES: Sequence[FeatureFunctionType] = (
    add_last_week_result,
    add_last_week_score,
    add_cum_percent,
    add_cum_win_points,
    add_rolling_pred_win_rate,
    add_rolling_last_week_win_rate,
    add_ladder_position,
    add_win_streak
)


class FeatureBuilder():
    """Add features to data frames.

    Args:
        feature_funcs (iterable): Iterable containing instances of Feature.
        oppo_feature_cols (list): List of column names for columns to convert to 'oppo'
            columns, then add to the data frame

    Attributes:
        feature_funcs (iterable): Iterable containing instances of Feature.
        oppo_feature_cols (list): List of column names for columns to convert to 'oppo'
            columns, then add to the data frame
    """

    def __init__(self,
                 feature_funcs: Sequence[FeatureFunctionType] = DEFAULT_FEATURES,
                 oppo_feature_cols: List[str] = []) -> None:
        self.feature_funcs = [
            self.__build_feature_function(feature_func) for feature_func in feature_funcs
        ]
        self._compose_all = reduce(
            self.__compose_two, reversed(self.feature_funcs), lambda x: x
        )
        self.oppo_feature_cols = oppo_feature_cols

    def transform(self, data_frame: pd.DataFrame) -> pd.DataFrame:
        """Add new features to the given data frame."""

        required_cols = REQUIRED_COLS + self.oppo_feature_cols

        if any((req_col not in data_frame.columns for req_col in required_cols)):
            raise ValueError('To calculate opposition column, all required columns '
                             f'({required_cols}) must be in data frame, '
                             f'but the columns given were {data_frame.columns}')

        transform_data_frame = (data_frame
                                .copy()
                                .set_index(INDEX_COLS, drop=False)
                                .sort_index())

        return self._compose_all(
            pd.concat(
                [transform_data_frame,
                 self.__oppo_features(transform_data_frame, self.oppo_feature_cols)],
                axis=1
            )
        )

    def __build_feature_function(self, feature_func: FeatureFunctionType) -> FeatureFunctionType:
        """Build a partial function function with the given feature function argument set"""

        return partial(self.__add_feature, feature_func)

    def __add_feature(self, feature_func: FeatureFunctionType,
                      data_frame: pd.DataFrame) -> pd.DataFrame:
        """Use the given feature function to add the feature and opposition team feature
        to the data frame"""

        if data_frame.index.names != INDEX_COLS:
            raise ValueError('To calculate opposition column, the indexes must be '
                             f'{INDEX_COLS}, but the data frame given has index names '
                             f'{data_frame.index.names}.')

        new_data_frame = feature_func(data_frame)

        # Get the new column label to add an 'oppo_' team version
        new_feature_labels = np.setdiff1d(new_data_frame.columns,
                                          data_frame.columns)

        if any(new_feature_labels):
            return pd.concat(
                [new_data_frame,
                 self.__oppo_features(new_data_frame, new_feature_labels)],
                axis=1
            )

        return new_data_frame

    @staticmethod
    def __compose_two(composed_func: FeatureFunctionType,
                      func_element: FeatureFunctionType) -> FeatureFunctionType:
        return lambda x: composed_func(func_element(x))

    @staticmethod
    def __oppo_features(data_frame: pd.DataFrame, col_names: List[str]) -> pd.DataFrame:
        """Add the same features, but for the current opposition team"""

        oppo_cols = {
            col_name: f'oppo_{col_name}' for col_name in col_names
        }
        column_translations = {
            **{'oppo_team': 'team'},
            **oppo_cols
        }

        return (data_frame
                .loc[:, ['year', 'round_number', 'oppo_team'] + col_names]
                # We switch out oppo_team for team in the index,
                # then assign feature as oppo_{feature_column}
                .rename(columns=column_translations)
                .set_index(INDEX_COLS)
                .sort_index()
                .loc[:, list(oppo_cols.keys())])
