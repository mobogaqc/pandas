import numpy as np
import pytest

import pandas as pd
import pandas._testing as tm
from pandas.api.indexers import check_array_indexer


@pytest.mark.parametrize(
    "indexer, expected",
    [
        # integer
        ([1, 2], np.array([1, 2], dtype=np.intp)),
        (np.array([1, 2], dtype="int64"), np.array([1, 2], dtype=np.intp)),
        (pd.array([1, 2], dtype="Int32"), np.array([1, 2], dtype=np.intp)),
        (pd.Index([1, 2]), np.array([1, 2], dtype=np.intp)),
        # boolean
        ([True, False, True], np.array([True, False, True], dtype=np.bool_)),
        (np.array([True, False, True]), np.array([True, False, True], dtype=np.bool_)),
        (
            pd.array([True, False, True], dtype="boolean"),
            np.array([True, False, True], dtype=np.bool_),
        ),
        # other
        ([], np.array([], dtype=np.intp)),
    ],
)
def test_valid_input(indexer, expected):
    array = np.array([1, 2, 3])
    result = check_array_indexer(array, indexer)
    tm.assert_numpy_array_equal(result, expected)


@pytest.mark.parametrize(
    "indexer", [[True, False, None], pd.array([True, False, None], dtype="boolean")],
)
def test_bool_raise_missing_values(indexer):
    array = np.array([1, 2, 3])

    msg = "Cannot mask with a boolean indexer containing NA values"
    with pytest.raises(ValueError, match=msg):
        check_array_indexer(array, indexer)


@pytest.mark.parametrize(
    "indexer",
    [
        [True, False],
        pd.array([True, False], dtype="boolean"),
        np.array([True, False], dtype=np.bool_),
    ],
)
def test_bool_raise_length(indexer):
    array = np.array([1, 2, 3])

    msg = "Boolean index has wrong length"
    with pytest.raises(IndexError, match=msg):
        check_array_indexer(array, indexer)


@pytest.mark.parametrize(
    "indexer", [[0, 1, None], pd.array([0, 1, pd.NA], dtype="Int64")],
)
def test_int_raise_missing_values(indexer):
    array = np.array([1, 2, 3])

    msg = "Cannot index with an integer indexer containing NA values"
    with pytest.raises(ValueError, match=msg):
        check_array_indexer(array, indexer)


@pytest.mark.parametrize(
    "indexer",
    [
        [0.0, 1.0],
        np.array([1.0, 2.0], dtype="float64"),
        np.array([True, False], dtype=object),
        pd.Index([True, False], dtype=object),
        pd.array(["a", "b"], dtype="string"),
    ],
)
def test_raise_invalid_array_dtypes(indexer):
    array = np.array([1, 2, 3])

    msg = "arrays used as indices must be of integer or boolean type"
    with pytest.raises(IndexError, match=msg):
        check_array_indexer(array, indexer)


@pytest.mark.parametrize(
    "indexer", [None, Ellipsis, slice(0, 3), (None,)],
)
def test_pass_through_non_array_likes(indexer):
    array = np.array([1, 2, 3])

    result = check_array_indexer(array, indexer)
    assert result == indexer
