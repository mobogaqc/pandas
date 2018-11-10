# -*- coding: utf-8 -*-

import numpy as np
import pytest

from pandas import Categorical, CategoricalIndex, Index, PeriodIndex, Series
import pandas.core.common as com
from pandas.tests.arrays.categorical.common import TestCategorical
import pandas.util.testing as tm


class TestCategoricalIndexingWithFactor(TestCategorical):

    def test_getitem(self):
        assert self.factor[0] == 'a'
        assert self.factor[-1] == 'c'

        subf = self.factor[[0, 1, 2]]
        tm.assert_numpy_array_equal(subf._codes,
                                    np.array([0, 1, 1], dtype=np.int8))

        subf = self.factor[np.asarray(self.factor) == 'c']
        tm.assert_numpy_array_equal(subf._codes,
                                    np.array([2, 2, 2], dtype=np.int8))

    def test_setitem(self):

        # int/positional
        c = self.factor.copy()
        c[0] = 'b'
        assert c[0] == 'b'
        c[-1] = 'a'
        assert c[-1] == 'a'

        # boolean
        c = self.factor.copy()
        indexer = np.zeros(len(c), dtype='bool')
        indexer[0] = True
        indexer[-1] = True
        c[indexer] = 'c'
        expected = Categorical(['c', 'b', 'b', 'a', 'a', 'c', 'c', 'c'],
                               ordered=True)

        tm.assert_categorical_equal(c, expected)


class TestCategoricalIndexing(object):

    def test_getitem_listlike(self):

        # GH 9469
        # properly coerce the input indexers
        np.random.seed(1)
        c = Categorical(np.random.randint(0, 5, size=150000).astype(np.int8))
        result = c.codes[np.array([100000]).astype(np.int64)]
        expected = c[np.array([100000]).astype(np.int64)].codes
        tm.assert_numpy_array_equal(result, expected)

    def test_periodindex(self):
        idx1 = PeriodIndex(['2014-01', '2014-01', '2014-02', '2014-02',
                            '2014-03', '2014-03'], freq='M')

        cat1 = Categorical(idx1)
        str(cat1)
        exp_arr = np.array([0, 0, 1, 1, 2, 2], dtype=np.int8)
        exp_idx = PeriodIndex(['2014-01', '2014-02', '2014-03'], freq='M')
        tm.assert_numpy_array_equal(cat1._codes, exp_arr)
        tm.assert_index_equal(cat1.categories, exp_idx)

        idx2 = PeriodIndex(['2014-03', '2014-03', '2014-02', '2014-01',
                            '2014-03', '2014-01'], freq='M')
        cat2 = Categorical(idx2, ordered=True)
        str(cat2)
        exp_arr = np.array([2, 2, 1, 0, 2, 0], dtype=np.int8)
        exp_idx2 = PeriodIndex(['2014-01', '2014-02', '2014-03'], freq='M')
        tm.assert_numpy_array_equal(cat2._codes, exp_arr)
        tm.assert_index_equal(cat2.categories, exp_idx2)

        idx3 = PeriodIndex(['2013-12', '2013-11', '2013-10', '2013-09',
                            '2013-08', '2013-07', '2013-05'], freq='M')
        cat3 = Categorical(idx3, ordered=True)
        exp_arr = np.array([6, 5, 4, 3, 2, 1, 0], dtype=np.int8)
        exp_idx = PeriodIndex(['2013-05', '2013-07', '2013-08', '2013-09',
                               '2013-10', '2013-11', '2013-12'], freq='M')
        tm.assert_numpy_array_equal(cat3._codes, exp_arr)
        tm.assert_index_equal(cat3.categories, exp_idx)

    def test_categories_assigments(self):
        s = Categorical(["a", "b", "c", "a"])
        exp = np.array([1, 2, 3, 1], dtype=np.int64)
        s.categories = [1, 2, 3]
        tm.assert_numpy_array_equal(s.__array__(), exp)
        tm.assert_index_equal(s.categories, Index([1, 2, 3]))

        # lengthen
        def f():
            s.categories = [1, 2, 3, 4]

        pytest.raises(ValueError, f)

        # shorten
        def f():
            s.categories = [1, 2]

        pytest.raises(ValueError, f)

    # Combinations of sorted/unique:
    @pytest.mark.parametrize("idx_values", [[1, 2, 3, 4], [1, 3, 2, 4],
                                            [1, 3, 3, 4], [1, 2, 2, 4]])
    # Combinations of missing/unique
    @pytest.mark.parametrize("key_values", [[1, 2], [1, 5], [1, 1], [5, 5]])
    @pytest.mark.parametrize("key_class", [Categorical, CategoricalIndex])
    def test_get_indexer_non_unique(self, idx_values, key_values, key_class):
        # GH 21448
        key = key_class(key_values, categories=range(1, 5))
        # Test for flat index and CategoricalIndex with same/different cats:
        for dtype in None, 'category', key.dtype:
            idx = Index(idx_values, dtype=dtype)
            expected, exp_miss = idx.get_indexer_non_unique(key_values)
            result, res_miss = idx.get_indexer_non_unique(key)

            tm.assert_numpy_array_equal(expected, result)
            tm.assert_numpy_array_equal(exp_miss, res_miss)


@pytest.mark.parametrize("index", [True, False])
def test_mask_with_boolean(index):
    s = Series(range(3))
    idx = Categorical([True, False, True])
    if index:
        idx = CategoricalIndex(idx)

    assert com.is_bool_indexer(idx)
    result = s[idx]
    expected = s[idx.astype('object')]
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize("index", [True, False])
def test_mask_with_boolean_raises(index):
    s = Series(range(3))
    idx = Categorical([True, False, None])
    if index:
        idx = CategoricalIndex(idx)

    with pytest.raises(ValueError, match='NA / NaN'):
        s[idx]
