import numpy as np
import pytest

import pandas as pd
from pandas import (
    Categorical, DataFrame, DatetimeIndex, Index, Interval, IntervalIndex,
    Series, TimedeltaIndex, Timestamp, cut, date_range, isna, qcut,
    timedelta_range, to_datetime)
from pandas.api.types import CategoricalDtype as CDT
import pandas.core.reshape.tile as tmod
import pandas.util.testing as tm


def test_simple():
    data = np.ones(5, dtype="int64")
    result = cut(data, 4, labels=False)

    expected = np.array([1, 1, 1, 1, 1])
    tm.assert_numpy_array_equal(result, expected, check_dtype=False)


def test_bins():
    data = np.array([.2, 1.4, 2.5, 6.2, 9.7, 2.1])
    result, bins = cut(data, 3, retbins=True)

    intervals = IntervalIndex.from_breaks(bins.round(3))
    intervals = intervals.take([0, 0, 0, 1, 2, 0])
    expected = Categorical(intervals, ordered=True)

    tm.assert_categorical_equal(result, expected)
    tm.assert_almost_equal(bins, np.array([0.1905, 3.36666667,
                                           6.53333333, 9.7]))


def test_right():
    data = np.array([.2, 1.4, 2.5, 6.2, 9.7, 2.1, 2.575])
    result, bins = cut(data, 4, right=True, retbins=True)

    intervals = IntervalIndex.from_breaks(bins.round(3))
    expected = Categorical(intervals, ordered=True)
    expected = expected.take([0, 0, 0, 2, 3, 0, 0])

    tm.assert_categorical_equal(result, expected)
    tm.assert_almost_equal(bins, np.array([0.1905, 2.575, 4.95, 7.325, 9.7]))


def test_no_right():
    data = np.array([.2, 1.4, 2.5, 6.2, 9.7, 2.1, 2.575])
    result, bins = cut(data, 4, right=False, retbins=True)

    intervals = IntervalIndex.from_breaks(bins.round(3), closed="left")
    intervals = intervals.take([0, 0, 0, 2, 3, 0, 1])
    expected = Categorical(intervals, ordered=True)

    tm.assert_categorical_equal(result, expected)
    tm.assert_almost_equal(bins, np.array([0.2, 2.575, 4.95, 7.325, 9.7095]))


def test_array_like():
    data = [.2, 1.4, 2.5, 6.2, 9.7, 2.1]
    result, bins = cut(data, 3, retbins=True)

    intervals = IntervalIndex.from_breaks(bins.round(3))
    intervals = intervals.take([0, 0, 0, 1, 2, 0])
    expected = Categorical(intervals, ordered=True)

    tm.assert_categorical_equal(result, expected)
    tm.assert_almost_equal(bins, np.array([0.1905, 3.36666667,
                                           6.53333333, 9.7]))


def test_bins_from_interval_index():
    c = cut(range(5), 3)
    expected = c
    result = cut(range(5), bins=expected.categories)
    tm.assert_categorical_equal(result, expected)

    expected = Categorical.from_codes(np.append(c.codes, -1),
                                      categories=c.categories,
                                      ordered=True)
    result = cut(range(6), bins=expected.categories)
    tm.assert_categorical_equal(result, expected)


def test_bins_from_interval_index_doc_example():
    # Make sure we preserve the bins.
    ages = np.array([10, 15, 13, 12, 23, 25, 28, 59, 60])
    c = cut(ages, bins=[0, 18, 35, 70])
    expected = IntervalIndex.from_tuples([(0, 18), (18, 35), (35, 70)])
    tm.assert_index_equal(c.categories, expected)

    result = cut([25, 20, 50], bins=c.categories)
    tm.assert_index_equal(result.categories, expected)
    tm.assert_numpy_array_equal(result.codes,
                                np.array([1, 1, 2], dtype="int8"))


def test_bins_not_overlapping_from_interval_index():
    # see gh-23980
    msg = "Overlapping IntervalIndex is not accepted"
    ii = IntervalIndex.from_tuples([(0, 10), (2, 12), (4, 14)])

    with pytest.raises(ValueError, match=msg):
        cut([5, 6], bins=ii)


def test_bins_not_monotonic():
    msg = "bins must increase monotonically"
    data = [.2, 1.4, 2.5, 6.2, 9.7, 2.1]

    with pytest.raises(ValueError, match=msg):
        cut(data, [0.1, 1.5, 1, 10])


def test_wrong_num_labels():
    msg = "Bin labels must be one fewer than the number of bin edges"
    data = [.2, 1.4, 2.5, 6.2, 9.7, 2.1]

    with pytest.raises(ValueError, match=msg):
        cut(data, [0, 1, 10], labels=["foo", "bar", "baz"])


@pytest.mark.parametrize("x,bins,msg", [
    ([], 2, "Cannot cut empty array"),
    ([1, 2, 3], 0.5, "`bins` should be a positive integer")
])
def test_cut_corner(x, bins, msg):
    with pytest.raises(ValueError, match=msg):
        cut(x, bins)


@pytest.mark.parametrize("arg", [2, np.eye(2), DataFrame(np.eye(2))])
@pytest.mark.parametrize("cut_func", [cut, qcut])
def test_cut_not_1d_arg(arg, cut_func):
    msg = "Input array must be 1 dimensional"
    with pytest.raises(ValueError, match=msg):
        cut_func(arg, 2)


def test_cut_out_of_range_more():
    # see gh-1511
    name = "x"

    ser = Series([0, -1, 0, 1, -3], name=name)
    ind = cut(ser, [0, 1], labels=False)

    exp = Series([np.nan, np.nan, np.nan, 0, np.nan], name=name)
    tm.assert_series_equal(ind, exp)


@pytest.mark.parametrize("right,breaks,closed", [
    (True, [-1e-3, 0.25, 0.5, 0.75, 1], "right"),
    (False, [0, 0.25, 0.5, 0.75, 1 + 1e-3], "left")
])
def test_labels(right, breaks, closed):
    arr = np.tile(np.arange(0, 1.01, 0.1), 4)

    result, bins = cut(arr, 4, retbins=True, right=right)
    ex_levels = IntervalIndex.from_breaks(breaks, closed=closed)
    tm.assert_index_equal(result.categories, ex_levels)


def test_cut_pass_series_name_to_factor():
    name = "foo"
    ser = Series(np.random.randn(100), name=name)

    factor = cut(ser, 4)
    assert factor.name == name


def test_label_precision():
    arr = np.arange(0, 0.73, 0.01)
    result = cut(arr, 4, precision=2)

    ex_levels = IntervalIndex.from_breaks([-0.00072, 0.18, 0.36, 0.54, 0.72])
    tm.assert_index_equal(result.categories, ex_levels)


@pytest.mark.parametrize("labels", [None, False])
def test_na_handling(labels):
    arr = np.arange(0, 0.75, 0.01)
    arr[::3] = np.nan

    result = cut(arr, 4, labels=labels)
    result = np.asarray(result)

    expected = np.where(isna(arr), np.nan, result)
    tm.assert_almost_equal(result, expected)


def test_inf_handling():
    data = np.arange(6)
    data_ser = Series(data, dtype="int64")

    bins = [-np.inf, 2, 4, np.inf]
    result = cut(data, bins)
    result_ser = cut(data_ser, bins)

    ex_uniques = IntervalIndex.from_breaks(bins)
    tm.assert_index_equal(result.categories, ex_uniques)

    assert result[5] == Interval(4, np.inf)
    assert result[0] == Interval(-np.inf, 2)
    assert result_ser[5] == Interval(4, np.inf)
    assert result_ser[0] == Interval(-np.inf, 2)


def test_cut_out_of_bounds():
    arr = np.random.randn(100)
    result = cut(arr, [-1, 0, 1])

    mask = isna(result)
    ex_mask = (arr < -1) | (arr > 1)
    tm.assert_numpy_array_equal(mask, ex_mask)


@pytest.mark.parametrize("get_labels,get_expected", [
    (lambda labels: labels,
     lambda labels: Categorical(["Medium"] + 4 * ["Small"] +
                                ["Medium", "Large"],
                                categories=labels, ordered=True)),
    (lambda labels: Categorical.from_codes([0, 1, 2], labels),
     lambda labels: Categorical.from_codes([1] + 4 * [0] + [1, 2], labels))
])
def test_cut_pass_labels(get_labels, get_expected):
    bins = [0, 25, 50, 100]
    arr = [50, 5, 10, 15, 20, 30, 70]
    labels = ["Small", "Medium", "Large"]

    result = cut(arr, bins, labels=get_labels(labels))
    tm.assert_categorical_equal(result, get_expected(labels))


def test_cut_pass_labels_compat():
    # see gh-16459
    arr = [50, 5, 10, 15, 20, 30, 70]
    labels = ["Good", "Medium", "Bad"]

    result = cut(arr, 3, labels=labels)
    exp = cut(arr, 3, labels=Categorical(labels, categories=labels,
                                         ordered=True))
    tm.assert_categorical_equal(result, exp)


@pytest.mark.parametrize("x", [np.arange(11.), np.arange(11.) / 1e10])
def test_round_frac_just_works(x):
    # It works.
    cut(x, 2)


@pytest.mark.parametrize("val,precision,expected", [
    (-117.9998, 3, -118),
    (117.9998, 3, 118),
    (117.9998, 2, 118),
    (0.000123456, 2, 0.00012)
])
def test_round_frac(val, precision, expected):
    # see gh-1979
    result = tmod._round_frac(val, precision=precision)
    assert result == expected


def test_cut_return_intervals():
    ser = Series([0, 1, 2, 3, 4, 5, 6, 7, 8])
    result = cut(ser, 3)

    exp_bins = np.linspace(0, 8, num=4).round(3)
    exp_bins[0] -= 0.008

    expected = Series(IntervalIndex.from_breaks(exp_bins, closed="right").take(
        [0, 0, 0, 1, 1, 1, 2, 2, 2])).astype(CDT(ordered=True))
    tm.assert_series_equal(result, expected)


def test_series_ret_bins():
    # see gh-8589
    ser = Series(np.arange(4))
    result, bins = cut(ser, 2, retbins=True)

    expected = Series(IntervalIndex.from_breaks(
        [-0.003, 1.5, 3], closed="right").repeat(2)).astype(CDT(ordered=True))
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize("kwargs,msg", [
    (dict(duplicates="drop"), None),
    (dict(), "Bin edges must be unique"),
    (dict(duplicates="raise"), "Bin edges must be unique"),
    (dict(duplicates="foo"), "invalid value for 'duplicates' parameter")
])
def test_cut_duplicates_bin(kwargs, msg):
    # see gh-20947
    bins = [0, 2, 4, 6, 10, 10]
    values = Series(np.array([1, 3, 5, 7, 9]), index=["a", "b", "c", "d", "e"])

    if msg is not None:
        with pytest.raises(ValueError, match=msg):
            cut(values, bins, **kwargs)
    else:
        result = cut(values, bins, **kwargs)
        expected = cut(values, pd.unique(bins))
        tm.assert_series_equal(result, expected)


@pytest.mark.parametrize("data", [9.0, -9.0, 0.0])
@pytest.mark.parametrize("length", [1, 2])
def test_single_bin(data, length):
    # see gh-14652, gh-15428
    ser = Series([data] * length)
    result = cut(ser, 1, labels=False)

    expected = Series([0] * length)
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize(
    "array_1_writeable,array_2_writeable",
    [(True, True), (True, False), (False, False)])
def test_cut_read_only(array_1_writeable, array_2_writeable):
    # issue 18773
    array_1 = np.arange(0, 100, 10)
    array_1.flags.writeable = array_1_writeable

    array_2 = np.arange(0, 100, 10)
    array_2.flags.writeable = array_2_writeable

    hundred_elements = np.arange(100)
    tm.assert_categorical_equal(cut(hundred_elements, array_1),
                                cut(hundred_elements, array_2))


@pytest.mark.parametrize("conv", [
    lambda v: Timestamp(v),
    lambda v: to_datetime(v),
    lambda v: np.datetime64(v),
    lambda v: Timestamp(v).to_pydatetime(),
])
def test_datetime_bin(conv):
    data = [np.datetime64("2012-12-13"), np.datetime64("2012-12-15")]
    bin_data = ["2012-12-12", "2012-12-14", "2012-12-16"]

    expected = Series(IntervalIndex([
        Interval(Timestamp(bin_data[0]), Timestamp(bin_data[1])),
        Interval(Timestamp(bin_data[1]), Timestamp(bin_data[2]))])).astype(
        CDT(ordered=True))

    bins = [conv(v) for v in bin_data]
    result = Series(cut(data, bins=bins))
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize("data", [
    to_datetime(Series(["2013-01-01", "2013-01-02", "2013-01-03"])),
    [np.datetime64("2013-01-01"), np.datetime64("2013-01-02"),
     np.datetime64("2013-01-03")],
    np.array([np.datetime64("2013-01-01"), np.datetime64("2013-01-02"),
              np.datetime64("2013-01-03")]),
    DatetimeIndex(["2013-01-01", "2013-01-02", "2013-01-03"])
])
def test_datetime_cut(data):
    # see gh-14714
    #
    # Testing time data when it comes in various collection types.
    result, _ = cut(data, 3, retbins=True)
    expected = Series(IntervalIndex([
        Interval(Timestamp("2012-12-31 23:57:07.200000"),
                 Timestamp("2013-01-01 16:00:00")),
        Interval(Timestamp("2013-01-01 16:00:00"),
                 Timestamp("2013-01-02 08:00:00")),
        Interval(Timestamp("2013-01-02 08:00:00"),
                 Timestamp("2013-01-03 00:00:00"))])).astype(CDT(ordered=True))
    tm.assert_series_equal(Series(result), expected)


@pytest.mark.parametrize("bins", [
    3, [Timestamp("2013-01-01 04:57:07.200000"),
        Timestamp("2013-01-01 21:00:00"),
        Timestamp("2013-01-02 13:00:00"),
        Timestamp("2013-01-03 05:00:00")]])
@pytest.mark.parametrize("box", [list, np.array, Index, Series])
def test_datetime_tz_cut(bins, box):
    # see gh-19872
    tz = "US/Eastern"
    s = Series(date_range("20130101", periods=3, tz=tz))

    if not isinstance(bins, int):
        bins = box(bins)

    result = cut(s, bins)
    expected = Series(IntervalIndex([
        Interval(Timestamp("2012-12-31 23:57:07.200000", tz=tz),
                 Timestamp("2013-01-01 16:00:00", tz=tz)),
        Interval(Timestamp("2013-01-01 16:00:00", tz=tz),
                 Timestamp("2013-01-02 08:00:00", tz=tz)),
        Interval(Timestamp("2013-01-02 08:00:00", tz=tz),
                 Timestamp("2013-01-03 00:00:00", tz=tz))])).astype(
        CDT(ordered=True))
    tm.assert_series_equal(result, expected)


def test_datetime_nan_error():
    msg = "bins must be of datetime64 dtype"

    with pytest.raises(ValueError, match=msg):
        cut(date_range("20130101", periods=3), bins=[0, 2, 4])


def test_datetime_nan_mask():
    result = cut(date_range("20130102", periods=5),
                 bins=date_range("20130101", periods=2))

    mask = result.categories.isna()
    tm.assert_numpy_array_equal(mask, np.array([False]))

    mask = result.isna()
    tm.assert_numpy_array_equal(mask, np.array([False, True, True,
                                                True, True]))


@pytest.mark.parametrize("tz", [None, "UTC", "US/Pacific"])
def test_datetime_cut_roundtrip(tz):
    # see gh-19891
    ser = Series(date_range("20180101", periods=3, tz=tz))
    result, result_bins = cut(ser, 2, retbins=True)

    expected = cut(ser, result_bins)
    tm.assert_series_equal(result, expected)

    expected_bins = DatetimeIndex(["2017-12-31 23:57:07.200000",
                                   "2018-01-02 00:00:00",
                                   "2018-01-03 00:00:00"])
    expected_bins = expected_bins.tz_localize(tz)
    tm.assert_index_equal(result_bins, expected_bins)


def test_timedelta_cut_roundtrip():
    # see gh-19891
    ser = Series(timedelta_range("1day", periods=3))
    result, result_bins = cut(ser, 2, retbins=True)

    expected = cut(ser, result_bins)
    tm.assert_series_equal(result, expected)

    expected_bins = TimedeltaIndex(["0 days 23:57:07.200000",
                                    "2 days 00:00:00",
                                    "3 days 00:00:00"])
    tm.assert_index_equal(result_bins, expected_bins)
