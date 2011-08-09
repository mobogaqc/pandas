from datetime import datetime, timedelta
import operator
import pickle
import unittest

import numpy as np

from pandas.core.index import Index, Factor, MultiIndex, NULL_INDEX
from pandas.util.testing import assert_almost_equal
import pandas.util.testing as common
import pandas._tseries as tseries

class TestIndex(unittest.TestCase):

    def setUp(self):
        self.strIndex = common.makeStringIndex(100)
        self.dateIndex = common.makeDateIndex(100)
        self.intIndex = common.makeIntIndex(100)
        self.empty = Index([])
        self.tuples = Index(zip(['foo', 'bar', 'baz'], [1, 2, 3]))

    def test_hash_error(self):
        self.assertRaises(TypeError, hash, self.strIndex)

    def test_deepcopy(self):
        from copy import deepcopy

        copy = deepcopy(self.strIndex)
        self.assert_(copy is self.strIndex)

    def test_duplicates(self):
        idx = Index([0, 0, 0])
        self.assertRaises(Exception, idx._verify_integrity)

    def test_sort(self):
        self.assertRaises(Exception, self.strIndex.sort)

    def test_mutability(self):
        self.assertRaises(Exception, self.strIndex.__setitem__, 5, 0)
        self.assertRaises(Exception, self.strIndex.__setitem__, slice(1,5), 0)

    def test_constructor(self):
        # regular instance creation
        common.assert_contains_all(self.strIndex, self.strIndex)
        common.assert_contains_all(self.dateIndex, self.dateIndex)

        # casting
        arr = np.array(self.strIndex)
        index = arr.view(Index)
        common.assert_contains_all(arr, index)
        self.assert_(np.array_equal(self.strIndex, index))

        # what to do here?
        # arr = np.array(5.)
        # self.assertRaises(Exception, arr.view, Index)

    def test_constructor_corner(self):
        # corner case
        self.assertRaises(Exception, Index, 0)

    def test_compat(self):
        self.strIndex.tolist()

    def test_equals(self):
        # same
        self.assert_(Index(['a', 'b', 'c']).equals(Index(['a', 'b', 'c'])))

        # different length
        self.assertFalse(Index(['a', 'b', 'c']).equals(Index(['a', 'b'])))

        # same length, different values
        self.assertFalse(Index(['a', 'b', 'c']).equals(Index(['a', 'b', 'd'])))

        # Must also be an Index
        self.assertFalse(Index(['a', 'b', 'c']).equals(['a', 'b', 'c']))

    def test_asOfDate(self):
        d = self.dateIndex[0]
        self.assert_(self.dateIndex.asOfDate(d) is d)
        self.assert_(self.dateIndex.asOfDate(d - timedelta(1)) is None)

        d = self.dateIndex[-1]
        self.assert_(self.dateIndex.asOfDate(d + timedelta(1)) is d)

    def test_argsort(self):
        result = self.strIndex.argsort()
        expected = np.array(self.strIndex).argsort()
        self.assert_(np.array_equal(result, expected))

    def test_comparators(self):
        index = self.dateIndex
        element = index[len(index) // 2]
        arr = np.array(index)

        def _check(op):
            arr_result = op(arr, element)
            index_result = op(index, element)

            self.assert_(isinstance(index_result, np.ndarray))
            self.assert_(not isinstance(index_result, Index))
            self.assert_(np.array_equal(arr_result, index_result))

        _check(operator.eq)
        _check(operator.ne)
        _check(operator.gt)
        _check(operator.lt)
        _check(operator.ge)
        _check(operator.le)

    def test_booleanindex(self):
        boolIdx = np.repeat(True, len(self.strIndex)).astype(bool)
        boolIdx[5:30:2] = False

        subIndex = self.strIndex[boolIdx]
        common.assert_dict_equal(tseries.map_indices(subIndex),
                                 subIndex.indexMap)

        subIndex = self.strIndex[list(boolIdx)]
        common.assert_dict_equal(tseries.map_indices(subIndex),
                                 subIndex.indexMap)

    def test_fancy(self):
        sl = self.strIndex[[1,2,3]]
        for i in sl:
            self.assertEqual(i, sl[sl.indexMap[i]])

    def test_getitem(self):
        arr = np.array(self.dateIndex)
        self.assertEquals(self.dateIndex[5], arr[5])

    def test_shift(self):
        shifted = self.dateIndex.shift(0, timedelta(1))
        self.assert_(shifted is self.dateIndex)

        shifted = self.dateIndex.shift(5, timedelta(1))
        self.assert_(np.array_equal(shifted, self.dateIndex + timedelta(5)))

    def test_intersection(self):
        first = self.strIndex[:20]
        second = self.strIndex[:10]
        intersect = first.intersection(second)

        self.assert_(common.equalContents(intersect, second))

        # Corner cases
        inter = first.intersection(first)
        self.assert_(inter is first)

        # non-iterable input
        self.assertRaises(Exception, first.intersection, 0.5)

    def test_union(self):
        first = self.strIndex[5:20]
        second = self.strIndex[:10]
        everything = self.strIndex[:20]
        union = first.union(second)
        self.assert_(common.equalContents(union, everything))

        # Corner cases
        union = first.union(first)
        self.assert_(union is first)

        union = first.union([])
        self.assert_(union is first)

        # non-iterable input
        self.assertRaises(Exception, first.union, 0.5)

    def test_add(self):
        firstCat = self.strIndex + self.dateIndex
        secondCat = self.strIndex + self.strIndex

        self.assert_(common.equalContents(np.append(self.strIndex,
                                                    self.dateIndex), firstCat))
        self.assert_(common.equalContents(secondCat, self.strIndex))
        common.assert_contains_all(self.strIndex, firstCat.indexMap)
        common.assert_contains_all(self.strIndex, secondCat.indexMap)
        common.assert_contains_all(self.dateIndex, firstCat.indexMap)

        # this is valid too
        shifted = self.dateIndex + timedelta(1)

    def test_add_string(self):
        # from bug report
        index = Index(['a', 'b', 'c'])
        index2 = index + 'foo'

        self.assert_('a' not in index2.indexMap)
        self.assert_('afoo' in index2.indexMap)

    def test_diff(self):
        first = self.strIndex[5:20]
        second = self.strIndex[:10]
        answer = self.strIndex[10:20]
        result = first - second

        self.assert_(common.equalContents(result, answer))

        diff = first.diff(first)
        self.assert_(len(diff) == 0)

        # non-iterable input
        self.assertRaises(Exception, first.diff, 0.5)

    def test_pickle(self):
        def testit(index):
            pickled = pickle.dumps(index)
            unpickled = pickle.loads(pickled)

            self.assert_(isinstance(unpickled, Index))
            self.assert_(np.array_equal(unpickled, index))

            common.assert_dict_equal(unpickled.indexMap, index.indexMap)

        testit(self.strIndex)
        testit(self.dateIndex)

    # def test_always_get_null_index(self):
    #     empty = Index([])
    #     self.assert_(empty is NULL_INDEX)
    #     self.assert_(self.dateIndex[15:15] is NULL_INDEX)

    def test_is_all_dates(self):
        self.assert_(self.dateIndex.is_all_dates())
        self.assert_(not self.strIndex.is_all_dates())
        self.assert_(not self.intIndex.is_all_dates())

    def test_summary(self):
        self._check_method_works(Index.summary)

    def test_format(self):
        self._check_method_works(Index.format)

        index = Index([datetime.now()])
        formatted = index.format()
        expected = str(index[0])
        self.assertEquals(formatted, expected)

    def test_take(self):
        indexer = [4, 3, 0, 2]
        result = self.dateIndex.take(indexer)
        expected = self.dateIndex[indexer]
        self.assert_(result.equals(expected))

    def _check_method_works(self, method):
        method(self.empty)
        method(self.dateIndex)
        method(self.strIndex)
        method(self.intIndex)
        method(self.tuples)

    def test_get_indexer(self):
        idx1 = Index([1, 2, 3, 4, 5])
        idx2 = Index([2, 4, 6])

        r1, r2 = idx1.get_indexer(idx2)
        assert_almost_equal(r1, [1, 3, -1])
        assert_almost_equal(r2, [True, True, False])

        r1, r2 = idx2.get_indexer(idx1, method='pad')
        assert_almost_equal(r1, [-1, 0, 0, 1, 1])
        assert_almost_equal(r2, [False, True, True, True, True])

        rffill1, rffill2 = idx2.get_indexer(idx1, method='ffill')
        assert_almost_equal(r1, rffill1)
        assert_almost_equal(r2, rffill2)

        r1, r2 = idx2.get_indexer(idx1, method='backfill')
        assert_almost_equal(r1, [0, 0, 1, 1, 2])
        assert_almost_equal(r2, [True, True, True, True, True])

        rbfill1, rbfill2 = idx2.get_indexer(idx1, method='bfill')
        assert_almost_equal(r1, rbfill1)
        assert_almost_equal(r2, rbfill2)

    def test_slice_locs(self):
        idx = Index([0, 1, 2, 5, 6, 7, 9, 10])
        n = len(idx)

        self.assertEquals(idx.slice_locs(start=2), (2, n))
        self.assertEquals(idx.slice_locs(start=3), (3, n))
        self.assertEquals(idx.slice_locs(3, 8), (3, 6))
        self.assertEquals(idx.slice_locs(5, 10), (3, n))
        self.assertEquals(idx.slice_locs(end=8), (0, 6))
        self.assertEquals(idx.slice_locs(end=9), (0, 7))

class TestMultiIndex(unittest.TestCase):

    def setUp(self):
        major_axis = Index(['foo', 'bar', 'baz', 'qux'])
        minor_axis = Index(['one', 'two'])

        major_labels = np.array([0, 0, 1, 2, 3, 3])
        minor_labels = np.array([0, 1, 0, 1, 0, 1])

        self.index = MultiIndex(levels=[major_axis, minor_axis],
                                labels=[major_labels, minor_labels])

    def test_from_arrays(self):
        arrays = []
        for lev, lab in zip(self.index.levels, self.index.labels):
            arrays.append(np.asarray(lev).take(lab))

        result = MultiIndex.from_arrays(arrays)
        self.assertEquals(list(result), list(self.index))

    def test_nlevels(self):
        self.assertEquals(self.index.nlevels, 2)

    def test_iter(self):
        result = list(self.index)
        expected = [('foo', 'one'), ('foo', 'two'), ('bar', 'one'),
                    ('baz', 'two'), ('qux', 'one'), ('qux', 'two')]
        self.assert_(result == expected)

    def test_pickle(self):
        import pickle
        pickled = pickle.dumps(self.index)
        unpickled = pickle.loads(pickled)
        self.assert_(self.index.equals(unpickled))

    def test_contains(self):
        self.assert_(('foo', 'two') in self.index)
        self.assert_(('bar', 'two') not in self.index)
        self.assert_(None not in self.index)

    def test_is_all_dates(self):
        self.assert_(not self.index.is_all_dates())

    def test_getitem(self):
        # scalar
        self.assertEquals(self.index[2], ('bar', 'one'))

        # slice
        result = self.index[2:5]
        expected = self.index[[2,3,4]]
        self.assert_(result.equals(expected))

        # boolean
        result = self.index[[True, False, True, False, True, True]]
        result2 = self.index[np.array([True, False, True, False, True, True])]
        expected = self.index[[0, 2, 4, 5]]
        self.assert_(result.equals(expected))
        self.assert_(result2.equals(expected))

    def test_getitem_group_select(self):
        sorted_idx, _ = self.index.sortlevel(0)
        self.assertEquals(sorted_idx.get_loc('baz'), slice(3, 4))
        self.assertEquals(sorted_idx.get_loc('foo'), slice(0, 2))

    def test_get_loc(self):
        self.assert_(self.index.get_loc(('foo', 'two')) == 1)
        self.assert_(self.index.get_loc(('baz', 'two')) == 3)
        self.assertRaises(KeyError, self.index.get_loc, ('bar', 'two'))

    def test_slice_locs_partial(self):
        sorted_idx, _ = self.index.sortlevel(0)
        result = sorted_idx.slice_locs(('foo', 'two'), ('qux', 'one'))
        self.assertEquals(result, (1, 5))

        result = sorted_idx.slice_locs(None, ('qux', 'one'))
        self.assertEquals(result, (0, 5))

        result = sorted_idx.slice_locs(('foo', 'two'), None)
        self.assertEquals(result, (1, len(sorted_idx)))

        result = sorted_idx.slice_locs('bar', 'baz')
        self.assertEquals(result, (2, 4))

    def test_slice_locs_not_contained(self):
        pass

    def test_consistency(self):
        # need to construct an overflow
        major_axis = range(70000)
        minor_axis = range(10)

        major_labels = np.arange(70000)
        minor_labels = np.repeat(range(10), 7000)

        # the fact that is works means it's consistent
        index = MultiIndex(levels=[major_axis, minor_axis],
                           labels=[major_labels, minor_labels])

        # inconsistent
        major_labels = np.array([0, 0, 1, 1, 1, 2, 2, 3, 3])
        minor_labels = np.array([0, 1, 0, 1, 1, 0, 1, 0, 1])
        index = MultiIndex(levels=[major_axis, minor_axis],
                           labels=[major_labels, minor_labels])

        self.assertRaises(Exception, getattr, index, 'indexMap')

    def test_truncate(self):
        major_axis = Index(range(4))
        minor_axis = Index(range(2))

        major_labels = np.array([0, 0, 1, 2, 3, 3])
        minor_labels = np.array([0, 1, 0, 1, 0, 1])

        index = MultiIndex(levels=[major_axis, minor_axis],
                           labels=[major_labels, minor_labels])

        result = index.truncate(before=1)
        self.assert_('foo' not in result.levels[0])
        self.assert_(1 in result.levels[0])

        result = index.truncate(after=1)
        self.assert_(2 not in result.levels[0])
        self.assert_(1 in result.levels[0])

        result = index.truncate(before=1, after=2)
        self.assertEqual(len(result.levels[0]), 2)

    def test_get_indexer(self):
        major_axis = Index(range(4))
        minor_axis = Index(range(2))

        major_labels = np.array([0, 0, 1, 2, 2, 3, 3])
        minor_labels = np.array([0, 1, 0, 0, 1, 0, 1])

        index = MultiIndex(levels=[major_axis, minor_axis],
                           labels=[major_labels, minor_labels])
        idx1 = index[:5]
        idx2 = index[[1,3,5]]

        r1, r2 = idx1.get_indexer(idx2)
        assert_almost_equal(r1, [1, 3, -1])
        assert_almost_equal(r2, [True, True, False])

        r1, r2 = idx2.get_indexer(idx1, method='pad')
        assert_almost_equal(r1, [-1, 0, 0, 1, 1])
        assert_almost_equal(r2, [False, True, True, True, True])

        rffill1, rffill2 = idx2.get_indexer(idx1, method='ffill')
        assert_almost_equal(r1, rffill1)
        assert_almost_equal(r2, rffill2)

        r1, r2 = idx2.get_indexer(idx1, method='backfill')
        assert_almost_equal(r1, [0, 0, 1, 1, 2])
        assert_almost_equal(r2, [True, True, True, True, True])

        rbfill1, rbfill2 = idx2.get_indexer(idx1, method='bfill')
        assert_almost_equal(r1, rbfill1)
        assert_almost_equal(r2, rbfill2)

        # pass non-MultiIndex
        self.assertRaises(Exception, idx1.get_indexer,
                          idx2.get_tuple_index())

    def test_format(self):
        self.index.format()

    def test_getMajorBounds(self):
        pass

    def test_getAxisBounds(self):
        pass

    def test_getLabelBounds(self):
        pass

    def test_bounds(self):
        pass

    def test_makeMask(self):
        from pandas.core.panel import make_mask

        mask =  make_mask(self.index)
        expected = np.array([True, True,
                             True, False,
                             False, True,
                             True, True], dtype=bool)
        self.assert_(np.array_equal(mask, expected))

    def test_dims(self):
        pass


class TestFactor(unittest.TestCase):

    def setUp(self):
        self.factor = Factor.fromarray(['a', 'b', 'b', 'a',
                                        'a', 'c', 'c', 'c'])

    def test_getitem(self):
        self.assertEqual(self.factor[0], 'a')
        self.assertEqual(self.factor[-1], 'c')

        subf = self.factor[[0, 1, 2]]
        common.assert_almost_equal(subf.labels, [0, 1, 1])

        subf = self.factor[self.factor.asarray() == 'c']
        common.assert_almost_equal(subf.labels, [2, 2, 2])

    def test_factor_agg(self):
        import pandas.core.frame as frame

        arr = np.arange(len(self.factor))

        f = np.sum
        agged = frame.factor_agg(self.factor, arr, f)
        labels = self.factor.labels
        for i, idx in enumerate(self.factor.levels):
            self.assertEqual(f(arr[labels == i]), agged[i])


if __name__ == '__main__':
    import nose
    nose.runmodule(argv=[__file__,'-vvs','-x','--pdb', '--pdb-failure',#]
                         '--with-coverage', '--cover-package=pandas.core'],
                   exit=False)

