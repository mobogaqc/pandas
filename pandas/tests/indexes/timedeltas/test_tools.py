from datetime import time, timedelta

import numpy as np
import pytest

from pandas._libs.tslib import iNaT

import pandas as pd
from pandas import Series, TimedeltaIndex, isna, to_timedelta
import pandas.util.testing as tm


class TestTimedeltas:
    def test_to_timedelta(self):
        def conv(v):
            return v.astype("m8[ns]")

        d1 = np.timedelta64(1, "D")

        with tm.assert_produces_warning(FutureWarning):
            assert to_timedelta("1 days 06:05:01.00003", box=False) == conv(
                d1
                + np.timedelta64(6 * 3600 + 5 * 60 + 1, "s")
                + np.timedelta64(30, "us")
            )

        with tm.assert_produces_warning(FutureWarning):
            assert to_timedelta("15.5us", box=False) == conv(
                np.timedelta64(15500, "ns")
            )

            # empty string
            result = to_timedelta("", box=False)
            assert result.astype("int64") == iNaT

        result = to_timedelta(["", ""])
        assert isna(result).all()

        # pass thru
        result = to_timedelta(np.array([np.timedelta64(1, "s")]))
        expected = pd.Index(np.array([np.timedelta64(1, "s")]))
        tm.assert_index_equal(result, expected)

        with tm.assert_produces_warning(FutureWarning):
            # ints
            result = np.timedelta64(0, "ns")
            expected = to_timedelta(0, box=False)
            assert result == expected

        # Series
        expected = Series([timedelta(days=1), timedelta(days=1, seconds=1)])
        result = to_timedelta(Series(["1d", "1days 00:00:01"]))
        tm.assert_series_equal(result, expected)

        # with units
        result = TimedeltaIndex(
            [np.timedelta64(0, "ns"), np.timedelta64(10, "s").astype("m8[ns]")]
        )
        expected = to_timedelta([0, 10], unit="s")
        tm.assert_index_equal(result, expected)

        with tm.assert_produces_warning(FutureWarning):
            # single element conversion
            v = timedelta(seconds=1)
            result = to_timedelta(v, box=False)
            expected = np.timedelta64(timedelta(seconds=1))
            assert result == expected

        with tm.assert_produces_warning(FutureWarning):
            v = np.timedelta64(timedelta(seconds=1))
            result = to_timedelta(v, box=False)
            expected = np.timedelta64(timedelta(seconds=1))
            assert result == expected

        # arrays of various dtypes
        arr = np.array([1] * 5, dtype="int64")
        result = to_timedelta(arr, unit="s")
        expected = TimedeltaIndex([np.timedelta64(1, "s")] * 5)
        tm.assert_index_equal(result, expected)

        arr = np.array([1] * 5, dtype="int64")
        result = to_timedelta(arr, unit="m")
        expected = TimedeltaIndex([np.timedelta64(1, "m")] * 5)
        tm.assert_index_equal(result, expected)

        arr = np.array([1] * 5, dtype="int64")
        result = to_timedelta(arr, unit="h")
        expected = TimedeltaIndex([np.timedelta64(1, "h")] * 5)
        tm.assert_index_equal(result, expected)

        arr = np.array([1] * 5, dtype="timedelta64[s]")
        result = to_timedelta(arr)
        expected = TimedeltaIndex([np.timedelta64(1, "s")] * 5)
        tm.assert_index_equal(result, expected)

        arr = np.array([1] * 5, dtype="timedelta64[D]")
        result = to_timedelta(arr)
        expected = TimedeltaIndex([np.timedelta64(1, "D")] * 5)
        tm.assert_index_equal(result, expected)

        with tm.assert_produces_warning(FutureWarning):
            # Test with lists as input when box=false
            expected = np.array(np.arange(3) * 1000000000, dtype="timedelta64[ns]")
            result = to_timedelta(range(3), unit="s", box=False)
            tm.assert_numpy_array_equal(expected, result)

        with tm.assert_produces_warning(FutureWarning):
            result = to_timedelta(np.arange(3), unit="s", box=False)
            tm.assert_numpy_array_equal(expected, result)

        with tm.assert_produces_warning(FutureWarning):
            result = to_timedelta([0, 1, 2], unit="s", box=False)
            tm.assert_numpy_array_equal(expected, result)

        with tm.assert_produces_warning(FutureWarning):
            # Tests with fractional seconds as input:
            expected = np.array(
                [0, 500000000, 800000000, 1200000000], dtype="timedelta64[ns]"
            )
            result = to_timedelta([0.0, 0.5, 0.8, 1.2], unit="s", box=False)
            tm.assert_numpy_array_equal(expected, result)

    def test_to_timedelta_invalid(self):

        # bad value for errors parameter
        msg = "errors must be one of"
        with pytest.raises(ValueError, match=msg):
            to_timedelta(["foo"], errors="never")

        # these will error
        msg = "invalid unit abbreviation: foo"
        with pytest.raises(ValueError, match=msg):
            to_timedelta([1, 2], unit="foo")
        with pytest.raises(ValueError, match=msg):
            to_timedelta(1, unit="foo")

        # time not supported ATM
        msg = (
            "Value must be Timedelta, string, integer, float, timedelta or"
            " convertible"
        )
        with pytest.raises(ValueError, match=msg):
            to_timedelta(time(second=1))
        assert to_timedelta(time(second=1), errors="coerce") is pd.NaT

        msg = "unit abbreviation w/o a number"
        with pytest.raises(ValueError, match=msg):
            to_timedelta(["foo", "bar"])
        tm.assert_index_equal(
            TimedeltaIndex([pd.NaT, pd.NaT]),
            to_timedelta(["foo", "bar"], errors="coerce"),
        )

        tm.assert_index_equal(
            TimedeltaIndex(["1 day", pd.NaT, "1 min"]),
            to_timedelta(["1 day", "bar", "1 min"], errors="coerce"),
        )

        # gh-13613: these should not error because errors='ignore'
        invalid_data = "apple"
        assert invalid_data == to_timedelta(invalid_data, errors="ignore")

        invalid_data = ["apple", "1 days"]
        tm.assert_numpy_array_equal(
            np.array(invalid_data, dtype=object),
            to_timedelta(invalid_data, errors="ignore"),
        )

        invalid_data = pd.Index(["apple", "1 days"])
        tm.assert_index_equal(invalid_data, to_timedelta(invalid_data, errors="ignore"))

        invalid_data = Series(["apple", "1 days"])
        tm.assert_series_equal(
            invalid_data, to_timedelta(invalid_data, errors="ignore")
        )

    def test_to_timedelta_via_apply(self):
        # GH 5458
        expected = Series([np.timedelta64(1, "s")])
        result = Series(["00:00:01"]).apply(to_timedelta)
        tm.assert_series_equal(result, expected)

        result = Series([to_timedelta("00:00:01")])
        tm.assert_series_equal(result, expected)

    def test_to_timedelta_on_missing_values(self):
        # GH5438
        timedelta_NaT = np.timedelta64("NaT")

        actual = pd.to_timedelta(Series(["00:00:01", np.nan]))
        expected = Series(
            [np.timedelta64(1000000000, "ns"), timedelta_NaT], dtype="<m8[ns]"
        )
        tm.assert_series_equal(actual, expected)

        actual = pd.to_timedelta(Series(["00:00:01", pd.NaT]))
        tm.assert_series_equal(actual, expected)

        actual = pd.to_timedelta(np.nan)
        assert actual.value == timedelta_NaT.astype("int64")

        actual = pd.to_timedelta(pd.NaT)
        assert actual.value == timedelta_NaT.astype("int64")

    def test_to_timedelta_float(self):
        # https://github.com/pandas-dev/pandas/issues/25077
        arr = np.arange(0, 1, 1e-6)[-10:]
        result = pd.to_timedelta(arr, unit="s")
        expected_asi8 = np.arange(999990000, int(1e9), 1000, dtype="int64")
        tm.assert_numpy_array_equal(result.asi8, expected_asi8)

    def test_to_timedelta_box_deprecated(self):
        result = np.timedelta64(0, "ns")

        # Deprecated - see GH24416
        with tm.assert_produces_warning(FutureWarning):
            to_timedelta(0, box=False)

        expected = to_timedelta(0).to_timedelta64()
        assert result == expected
