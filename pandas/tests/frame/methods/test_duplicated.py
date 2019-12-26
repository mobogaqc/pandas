import re

import numpy as np
import pytest

from pandas import DataFrame, Series
import pandas.util.testing as tm


@pytest.mark.parametrize("subset", ["a", ["a"], ["a", "B"]])
def test_duplicated_with_misspelled_column_name(subset):
    # GH 19730
    df = DataFrame({"A": [0, 0, 1], "B": [0, 0, 1], "C": [0, 0, 1]})
    msg = re.escape("Index(['a'], dtype='object')")

    with pytest.raises(KeyError, match=msg):
        df.duplicated(subset)


@pytest.mark.slow
def test_duplicated_do_not_fail_on_wide_dataframes():
    # gh-21524
    # Given the wide dataframe with a lot of columns
    # with different (important!) values
    data = {
        "col_{0:02d}".format(i): np.random.randint(0, 1000, 30000) for i in range(100)
    }
    df = DataFrame(data).T
    result = df.duplicated()

    # Then duplicates produce the bool Series as a result and don't fail during
    # calculation. Actual values doesn't matter here, though usually it's all
    # False in this case
    assert isinstance(result, Series)
    assert result.dtype == np.bool


@pytest.mark.parametrize(
    "keep, expected",
    [
        ("first", Series([False, False, True, False, True])),
        ("last", Series([True, True, False, False, False])),
        (False, Series([True, True, True, False, True])),
    ],
)
def test_duplicated_keep(keep, expected):
    df = DataFrame({"A": [0, 1, 1, 2, 0], "B": ["a", "b", "b", "c", "a"]})

    result = df.duplicated(keep=keep)
    tm.assert_series_equal(result, expected)


@pytest.mark.xfail(reason="GH#21720; nan/None falsely considered equal")
@pytest.mark.parametrize(
    "keep, expected",
    [
        ("first", Series([False, False, True, False, True])),
        ("last", Series([True, True, False, False, False])),
        (False, Series([True, True, True, False, True])),
    ],
)
def test_duplicated_nan_none(keep, expected):
    df = DataFrame({"C": [np.nan, 3, 3, None, np.nan]}, dtype=object)

    result = df.duplicated(keep=keep)
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize("keep", ["first", "last", False])
@pytest.mark.parametrize("subset", [None, ["A", "B"], "A"])
def test_duplicated_subset(subset, keep):
    df = DataFrame(
        {
            "A": [0, 1, 1, 2, 0],
            "B": ["a", "b", "b", "c", "a"],
            "C": [np.nan, 3, 3, None, np.nan],
        }
    )

    if subset is None:
        subset = list(df.columns)
    elif isinstance(subset, str):
        # need to have a DataFrame, not a Series
        # -> select columns with singleton list, not string
        subset = [subset]

    expected = df[subset].duplicated(keep=keep)
    result = df.duplicated(keep=keep, subset=subset)
    tm.assert_series_equal(result, expected)


def test_duplicated_on_empty_frame():
    # GH 25184

    df = DataFrame(columns=["a", "b"])
    dupes = df.duplicated("a")

    result = df[dupes]
    expected = df.copy()
    tm.assert_frame_equal(result, expected)
