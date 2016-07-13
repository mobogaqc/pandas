# -*- coding: utf-8 -*-

import nose
import numpy as np
from datetime import datetime
from pandas.util import testing as tm

from pandas.core import config as cf
from pandas.compat import u
from pandas.tslib import iNaT
from pandas import (NaT, Float64Index, Series,
                    DatetimeIndex, TimedeltaIndex, date_range)
from pandas.types.dtypes import DatetimeTZDtype
from pandas.types.missing import (array_equivalent, isnull, notnull,
                                  na_value_for_dtype)

_multiprocess_can_split_ = True


def test_notnull():
    assert notnull(1.)
    assert not notnull(None)
    assert not notnull(np.NaN)

    with cf.option_context("mode.use_inf_as_null", False):
        assert notnull(np.inf)
        assert notnull(-np.inf)

        arr = np.array([1.5, np.inf, 3.5, -np.inf])
        result = notnull(arr)
        assert result.all()

    with cf.option_context("mode.use_inf_as_null", True):
        assert not notnull(np.inf)
        assert not notnull(-np.inf)

        arr = np.array([1.5, np.inf, 3.5, -np.inf])
        result = notnull(arr)
        assert result.sum() == 2

    with cf.option_context("mode.use_inf_as_null", False):
        for s in [tm.makeFloatSeries(), tm.makeStringSeries(),
                  tm.makeObjectSeries(), tm.makeTimeSeries(),
                  tm.makePeriodSeries()]:
            assert (isinstance(isnull(s), Series))


def test_isnull():
    assert not isnull(1.)
    assert isnull(None)
    assert isnull(np.NaN)
    assert not isnull(np.inf)
    assert not isnull(-np.inf)

    # series
    for s in [tm.makeFloatSeries(), tm.makeStringSeries(),
              tm.makeObjectSeries(), tm.makeTimeSeries(),
              tm.makePeriodSeries()]:
        assert (isinstance(isnull(s), Series))

    # frame
    for df in [tm.makeTimeDataFrame(), tm.makePeriodFrame(),
               tm.makeMixedDataFrame()]:
        result = isnull(df)
        expected = df.apply(isnull)
        tm.assert_frame_equal(result, expected)

    # panel
    for p in [tm.makePanel(), tm.makePeriodPanel(), tm.add_nans(tm.makePanel())
              ]:
        result = isnull(p)
        expected = p.apply(isnull)
        tm.assert_panel_equal(result, expected)

    # panel 4d
    for p in [tm.makePanel4D(), tm.add_nans_panel4d(tm.makePanel4D())]:
        result = isnull(p)
        expected = p.apply(isnull)
        tm.assert_panel4d_equal(result, expected)


def test_isnull_lists():
    result = isnull([[False]])
    exp = np.array([[False]])
    assert (np.array_equal(result, exp))

    result = isnull([[1], [2]])
    exp = np.array([[False], [False]])
    assert (np.array_equal(result, exp))

    # list of strings / unicode
    result = isnull(['foo', 'bar'])
    assert (not result.any())

    result = isnull([u('foo'), u('bar')])
    assert (not result.any())


def test_isnull_nat():
    result = isnull([NaT])
    exp = np.array([True])
    assert (np.array_equal(result, exp))

    result = isnull(np.array([NaT], dtype=object))
    exp = np.array([True])
    assert (np.array_equal(result, exp))


def test_isnull_numpy_nat():
    arr = np.array([NaT, np.datetime64('NaT'), np.timedelta64('NaT'),
                    np.datetime64('NaT', 's')])
    result = isnull(arr)
    expected = np.array([True] * 4)
    tm.assert_numpy_array_equal(result, expected)


def test_isnull_datetime():
    assert (not isnull(datetime.now()))
    assert notnull(datetime.now())

    idx = date_range('1/1/1990', periods=20)
    assert (notnull(idx).all())

    idx = np.asarray(idx)
    idx[0] = iNaT
    idx = DatetimeIndex(idx)
    mask = isnull(idx)
    assert (mask[0])
    assert (not mask[1:].any())

    # GH 9129
    pidx = idx.to_period(freq='M')
    mask = isnull(pidx)
    assert (mask[0])
    assert (not mask[1:].any())

    mask = isnull(pidx[1:])
    assert (not mask.any())


class TestIsNull(tm.TestCase):

    def test_0d_array(self):
        self.assertTrue(isnull(np.array(np.nan)))
        self.assertFalse(isnull(np.array(0.0)))
        self.assertFalse(isnull(np.array(0)))
        # test object dtype
        self.assertTrue(isnull(np.array(np.nan, dtype=object)))
        self.assertFalse(isnull(np.array(0.0, dtype=object)))
        self.assertFalse(isnull(np.array(0, dtype=object)))


def test_array_equivalent():
    assert array_equivalent(np.array([np.nan, np.nan]),
                            np.array([np.nan, np.nan]))
    assert array_equivalent(np.array([np.nan, 1, np.nan]),
                            np.array([np.nan, 1, np.nan]))
    assert array_equivalent(np.array([np.nan, None], dtype='object'),
                            np.array([np.nan, None], dtype='object'))
    assert array_equivalent(np.array([np.nan, 1 + 1j], dtype='complex'),
                            np.array([np.nan, 1 + 1j], dtype='complex'))
    assert not array_equivalent(
        np.array([np.nan, 1 + 1j], dtype='complex'), np.array(
            [np.nan, 1 + 2j], dtype='complex'))
    assert not array_equivalent(
        np.array([np.nan, 1, np.nan]), np.array([np.nan, 2, np.nan]))
    assert not array_equivalent(
        np.array(['a', 'b', 'c', 'd']), np.array(['e', 'e']))
    assert array_equivalent(Float64Index([0, np.nan]),
                            Float64Index([0, np.nan]))
    assert not array_equivalent(
        Float64Index([0, np.nan]), Float64Index([1, np.nan]))
    assert array_equivalent(DatetimeIndex([0, np.nan]),
                            DatetimeIndex([0, np.nan]))
    assert not array_equivalent(
        DatetimeIndex([0, np.nan]), DatetimeIndex([1, np.nan]))
    assert array_equivalent(TimedeltaIndex([0, np.nan]),
                            TimedeltaIndex([0, np.nan]))
    assert not array_equivalent(
        TimedeltaIndex([0, np.nan]), TimedeltaIndex([1, np.nan]))
    assert array_equivalent(DatetimeIndex([0, np.nan], tz='US/Eastern'),
                            DatetimeIndex([0, np.nan], tz='US/Eastern'))
    assert not array_equivalent(
        DatetimeIndex([0, np.nan], tz='US/Eastern'), DatetimeIndex(
            [1, np.nan], tz='US/Eastern'))
    assert not array_equivalent(
        DatetimeIndex([0, np.nan]), DatetimeIndex(
            [0, np.nan], tz='US/Eastern'))
    assert not array_equivalent(
        DatetimeIndex([0, np.nan], tz='CET'), DatetimeIndex(
            [0, np.nan], tz='US/Eastern'))
    assert not array_equivalent(
        DatetimeIndex([0, np.nan]), TimedeltaIndex([0, np.nan]))


def test_array_equivalent_compat():
    # see gh-13388
    m = np.array([(1, 2), (3, 4)], dtype=[('a', int), ('b', float)])
    n = np.array([(1, 2), (3, 4)], dtype=[('a', int), ('b', float)])
    assert (array_equivalent(m, n, strict_nan=True))
    assert (array_equivalent(m, n, strict_nan=False))

    m = np.array([(1, 2), (3, 4)], dtype=[('a', int), ('b', float)])
    n = np.array([(1, 2), (4, 3)], dtype=[('a', int), ('b', float)])
    assert (not array_equivalent(m, n, strict_nan=True))
    assert (not array_equivalent(m, n, strict_nan=False))

    m = np.array([(1, 2), (3, 4)], dtype=[('a', int), ('b', float)])
    n = np.array([(1, 2), (3, 4)], dtype=[('b', int), ('a', float)])
    assert (not array_equivalent(m, n, strict_nan=True))
    assert (not array_equivalent(m, n, strict_nan=False))


def test_array_equivalent_str():
    for dtype in ['O', 'S', 'U']:
        assert array_equivalent(np.array(['A', 'B'], dtype=dtype),
                                np.array(['A', 'B'], dtype=dtype))
        assert not array_equivalent(np.array(['A', 'B'], dtype=dtype),
                                    np.array(['A', 'X'], dtype=dtype))


def test_na_value_for_dtype():
    for dtype in [np.dtype('M8[ns]'), np.dtype('m8[ns]'),
                  DatetimeTZDtype('datetime64[ns, US/Eastern]')]:
        assert na_value_for_dtype(dtype) is NaT

    for dtype in ['u1', 'u2', 'u4', 'u8',
                  'i1', 'i2', 'i4', 'i8']:
        assert na_value_for_dtype(np.dtype(dtype)) == 0

    for dtype in ['bool']:
        assert na_value_for_dtype(np.dtype(dtype)) is False

    for dtype in ['f2', 'f4', 'f8']:
        assert np.isnan(na_value_for_dtype(np.dtype(dtype)))

    for dtype in ['O']:
        assert np.isnan(na_value_for_dtype(np.dtype(dtype)))


if __name__ == '__main__':
    nose.runmodule(argv=[__file__, '-vvs', '-x', '--pdb', '--pdb-failure'],
                   exit=False)
