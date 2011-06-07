import itertools

from numpy import nan
import numpy as np

from pandas.core.index import Index, NULL_INDEX
from pandas.core.common import _ensure_index
from pandas.core.series import Series
import pandas.core.common as common

class Block(object):
    """
    Canonical unit of homogeneous dtype contained in DataMatrix
    """

    def __init__(self, values, columns):
        values = _convert_if_1d(values)
        self.values = values
        self.columns = _ensure_index(columns)

    def __repr__(self):
        x, y = self.shape
        return 'Block: %s, %d x %d, dtype %s' % (self.columns, x, y,
                                                 self.dtype)

    def __contains__(self, col):
        return col in self.columns

    def __len__(self):
        return len(self.values)

    @property
    def shape(self):
        return self.values.shape

    @property
    def dtype(self):
        return self.values.dtype

    def merge(self, other):
        return _merge_blocks([self, other])

    def reindex(self, new_columns):
        indexer, mask = self.columns.get_indexer(columns)
        new_values = self.values.take(indexer, axis=1)

        notmask = -mask
        if len(mask) > 0 and notmask.any():
            if issubclass(mat.dtype.type, np.int_):
                mat = mat.astype(float)
            elif issubclass(mat.dtype.type, np.bool_):
                mat = mat.astype(object)

            common.null_out_axis(mat, notmask, 1)

        return Block(new_values, columns)

    def insert(self, col, value, loc=None):
        """
        Insert new column into Block, return new Block

        Returns
        -------
        y : Block (new object)
        """
        assert(col not in self.columns)
        if loc is None:
            loc = len(self.columns)

        new_columns = _insert_into_columns(self.columns, col, loc)
        new_values = _insert_into_values(self.values, value, loc)
        return Block(new_values, new_columns)

    def set(self, col, value):
        """
        Modify Block in-place with new column value

        Returns
        -------
        None
        """
        loc = self.columns.get_loc(col)
        self.values[:, loc] = value

    def delete(self, col):
        """
        Returns
        -------
        y : Block (new object)
        """
        loc = self.columns.get_loc(col)
        new_columns = _delete_from_columns(self.columns, loc)
        new_values = _delete_from_values(self.values, loc)
        return Block(new_values, new_columns)

def _insert_into_columns(columns, col, loc):
    columns = np.asarray(columns)
    new_columns = np.insert(columns, loc, col)
    return Index(new_columns)

def _insert_into_values(values, new_vec, loc):
    return np.insert(values, loc, new_vec, 1)

def _delete_from_columns(columns, loc):
    columns = np.asarray(columns)
    new_columns = np.delete(columns, loc)
    return Index(new_columns)

def _delete_from_values(values, loc):
    return np.delete(values, loc, 1)

def _convert_if_1d(values):
    if values.ndim == 1:
        values = np.atleast_2d(values).T

    return values

class FloatBlock(Block):
    pass

class ObjectBlock(Block):
    pass

def make_block(values, columns):
    pass

# TODO: flexible with index=None and/or columns=None

class BlockManager(object):
    """
    Manage a bunch of labeled 2D mixed-type ndarrays. Essentially it's a
    lightweight blocked set of labeled data to be manipulated by the DataFrame
    public API class

    This is *not* a public API class
    """
    def __init__(self, blocks, index=None, columns=None):
        self.index = index
        self.columns = columns
        self.blocks = blocks

    def __repr__(self):
        output = 'BlockManager'
        for block in self.blocks:
            output += '\n%s' % repr(block)
        return output

    def _verify_integrity(self):
        _union_block_columns(self.columns)
        length = self.block_length
        for block in self.blocks:
            assert(len(block) == length)

    def get_slice(self, slice_obj):
        new_blocks = _slice_blocks(self.blocks, slice_obj)
        new_index = self.index[slice_obj]
        return BlockManager(new_blocks, index=new_index, columns=self.columns)

    def get_series_dict(self, index):
        return _blocks_to_series_dict(self.blocks, index)

    @property
    def block_length(self):
        return len(self.blocks[0])

    def __len__(self):
        # number of blocks
        return len(self.index)

    @classmethod
    def from_blocks(cls, blocks, index):
        # also checks for overlap
        columns = _union_block_columns(blocks)
        return BlockManager(blocks, columns)

    def __contains__(self, column):
        return column in self.columns

    @property
    def nblocks(self):
        return len(self.blocks)

    def as_matrix(self, columns=None):
        if columns is None:
            if self.nblocks == 0:
                return self.blocks.values[0]
            return _interleave(self.blocks, self.columns)
        else:
            return _interleave(self.blocks, columns)

    def xs(self, i, copy=True):
        return np.concatenate([b[i] for b in blocks])

    def consolidate(self):
        """

        Returns
        -------

        """

        new_blocks = _consolidate(self.blocks)
        return BlockManager(new_blocks, self.columns)

    def get(self, col):
        _, block = self._find_block(col)
        return block.get(col)

    def delete(self, col):
        i, block = self._find_block(col)
        new_block = block.delete(col)
        self.blocks[i] = new_block

    def set(self, col, value):
        """
        Set new column in-place. Does not consolidate. Adds new Block if not
        contained in the current set of columns
        """
        assert(len(value) == self.block_length)
        if col in self.columns:
            i, block = self._find_block(col)
            if _needs_other_dtype(block, value):
                # delete from block, create and append new block
                self.blocks[i] = block.delete(col)
                self._add_new_block(col, value)
        else:
            # new block
            self._add_new_block(col, value)

            # TODO: where to insert?
            self.columns = _insert_into_columns(self.columns, col,
                                                len(self.columns))

    def _add_new_block(self, col, value):
        # Do we care about dtype at the moment?
        new_block = Block(value, [col])
        self._push_new_block(new_block)

    def _find_block(self, col):
        self._check_have(col)
        for i, block in enumerate(self.blocks):
            if col in block:
                return i, block

        raise Exception('technically unreachable code')

    def _push_new_block(self, block):
        self.blocks.append(block)

    def _check_have(self, col):
        if col not in self.columns:
            raise KeyError('no column named %s' % col)

    def _chunk_index(self, col):
        pass

    def rename(self, mapper):
        pass

    def reindex_index(self, indexer, mask):
        mat = self.values.take(indexer, axis=0)

        notmask = -mask
        if len(index) > 0:
            if notmask.any():
                if issubclass(mat.dtype.type, np.int_):
                    mat = mat.astype(float)
                elif issubclass(mat.dtype.type, np.bool_):
                    mat = mat.astype(float)

                common.null_out_axis(mat, notmask, 0)

    def reindex_columns(self, new_columns):
        pass

def _slice_blocks(blocks, slice_obj):
    new_blocks = []
    for block in blocks:
        newb = Block(block.values[slice_obj], block.columns)
        new_blocks.append(newb)
    return new_blocks

# TODO!
def _needs_other_dtype(block, to_insert):
    if to_insert.dtype != block.dtype:
        pass

def _blocks_to_series_dict(blocks, index=None):
    series_dict = {}

    if index is None:
        index = Index(np.arange(len(blocks[0])))

    for block in blocks:
        for col, vec in zip(block.columns, block.values.T):
            series_dict[col] = Series(vec, index=index)
    return series_dict

def _insert_column(blocks, column, value):
    """
    Default: new block
    """
    pass

def _set_column(blocks, column, value):
    pass

def _delete_column(blocks, columns):
    pass

def _reindex_blocks(blocks, old_columns, new_columns):
    pass

def _interleave(blocks, columns):
    """
    Return ndarray from blocks with specified column order
    """
    dtype = _interleaved_dtype(blocks)
    columns = _ensure_index(columns)

    result = np.empty((len(blocks[0]), len(columns)), dtype=dtype)
    result.fill(nan)

    for block in blocks:
        indexer, mask = columns.get_indexer(block.columns)

        if mask.all():
            result[:, indexer] = block.values
        else:
            result[:, indexer[mask]] = block.values[mask]

    return result

def _interleaved_dtype(blocks):
    for block in blocks:
        if not issubclass(block.dtype.type, np.floating):
            return object
    return np.float64

def _consolidate(blocks):
    """
    Merge blocks having same dtype
    """
    get_dtype = lambda x: x.dtype

    # sort by dtype
    grouper = itertools.groupby(sorted(blocks, key=get_dtype),
                                lambda x: x.dtype)

    new_blocks = []
    for dtype, group_blocks in grouper:
        new_block = _merge_blocks(list(group_blocks))
        new_blocks.append(new_block)

    return new_blocks

def _merge_blocks(blocks):
    new_values = np.hstack([b.values for b in blocks])
    new_columns = np.concatenate([b.columns for b in blocks])
    new_block = Block(new_values, new_columns)
    return new_block

def _xs(blocks, i, copy=True):
    if copy:
        return np.concatenate([b[i] for b in blocks])
    else:
        if len(blocks) == 1:
            return blocks[0].values[i]
        else:
            raise Exception('cannot get view with mixed-type data')

def _union_block_columns(blocks):
    seen = Index([])

    for block in blocks:
        len_before = len(seen)
        seen = seen.union(block.columns)
        if len(seen) != len_before + len(block.columns):
            raise Exception('column names overlap')

    return seen

def _nan_manager_matching(index, columns):
    # what if one of these is empty?
    values = _nan_array(index, columns)
    block = Block(values, columns)
    return BlockManager([block], columns)

def _nan_array(index, columns):
    if index is None:
        index = NULL_INDEX
    if columns is None:
        columns = NULL_INDEX

    values = np.empty((len(index), len(columns)), dtype=dtype)
    values.fill(NaN)
    return values

import unittest
class TestBlockOperations(unittest.TestCase):

    def test_interleave(self):
        pass

    def test_consolidate(self):
        pass

    def test_xs(self):
        pass

if __name__ == '__main__':
    floats = np.repeat(np.atleast_2d(np.arange(3.)), 10, axis=0)
    objects = np.empty((10, 2), dtype=object)
    objects[:, 0] = 'foo'
    objects[:, 1] = 'bar'

    float_cols = Index(['a', 'c', 'e'])
    object_cols = Index(['b', 'd'])
    columns = Index(sorted(float_cols + object_cols))
    new_columns = Index(['a', 'c', 'e', 'b', 'd'])

    fblock = Block(floats, float_cols)
    oblock = Block(objects, object_cols)

    blocks = [fblock, oblock]

    interleaved = _interleave(blocks, columns)

    manager = BlockManager(blocks, columns)
