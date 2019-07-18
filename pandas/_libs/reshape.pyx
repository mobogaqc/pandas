import cython
from cython import Py_ssize_t

from numpy cimport (int8_t, int16_t, int32_t, int64_t, uint8_t, uint16_t,
                    uint32_t, uint64_t, float32_t, float64_t, ndarray)
cimport numpy as cnp
import numpy as np
from pandas._libs.lib cimport c_is_list_like
cnp.import_array()

ctypedef fused reshape_t:
    uint8_t
    uint16_t
    uint32_t
    uint64_t
    int8_t
    int16_t
    int32_t
    int64_t
    float32_t
    float64_t
    object


@cython.wraparound(False)
@cython.boundscheck(False)
def unstack(reshape_t[:, :] values, uint8_t[:] mask,
            Py_ssize_t stride, Py_ssize_t length, Py_ssize_t width,
            reshape_t[:, :] new_values, uint8_t[:, :] new_mask):
    """
    transform long sorted_values to wide new_values

    Parameters
    ----------
    values : typed ndarray
    mask : boolean ndarray
    stride : int
    length : int
    width : int
    new_values : typed ndarray
        result array
    new_mask : boolean ndarray
        result mask
    """
    cdef:
        Py_ssize_t i, j, w, nulls, s, offset

    if reshape_t is not object:
        # evaluated at compile-time
        with nogil:
            for i in range(stride):

                nulls = 0
                for j in range(length):

                    for w in range(width):

                        offset = j * width + w

                        if mask[offset]:
                            s = i * width + w
                            new_values[j, s] = values[offset - nulls, i]
                            new_mask[j, s] = 1
                        else:
                            nulls += 1

    else:
        # object-dtype, identical to above but we cannot use nogil
        for i in range(stride):

            nulls = 0
            for j in range(length):

                for w in range(width):

                    offset = j * width + w

                    if mask[offset]:
                        s = i * width + w
                        new_values[j, s] = values[offset - nulls, i]
                        new_mask[j, s] = 1
                    else:
                        nulls += 1


unstack_uint8 = unstack["uint8_t"]
unstack_uint16 = unstack["uint16_t"]
unstack_uint32 = unstack["uint32_t"]
unstack_uint64 = unstack["uint64_t"]
unstack_int8 = unstack["int8_t"]
unstack_int16 = unstack["int16_t"]
unstack_int32 = unstack["int32_t"]
unstack_int64 = unstack["int64_t"]
unstack_float32 = unstack["float32_t"]
unstack_float64 = unstack["float64_t"]
unstack_object = unstack["object"]


@cython.wraparound(False)
@cython.boundscheck(False)
def explode(ndarray[object] values):
    """
    transform array list-likes to long form
    preserve non-list entries

    Parameters
    ----------
    values : object ndarray

    Returns
    -------
    tuple(values, counts)
    """
    cdef:
        Py_ssize_t i, j, count, n
        object v
        ndarray[object] result
        ndarray[int64_t] counts

    # find the resulting len
    n = len(values)
    counts = np.zeros(n, dtype='int64')
    for i in range(n):
        v = values[i]
        if c_is_list_like(v, False):
            if len(v):
                counts[i] += len(v)
            else:
                # empty list-like, use a nan marker
                counts[i] += 1
        else:
            counts[i] += 1

    result = np.empty(counts.sum(), dtype='object')
    count = 0
    for i in range(n):
        v = values[i]

        if c_is_list_like(v, False):
            if len(v):
                for j in range(len(v)):
                    result[count] = v[j]
                    count += 1
            else:
                # empty list-like, use a nan marker
                result[count] = np.nan
                count += 1
        else:
            # replace with the existing scalar
            result[count] = v
            count += 1
    return result, counts
