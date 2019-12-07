/*
Copyright (c) 2011-2013, ESN Social Software AB and Jonas Tarnstrom
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
* Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright
notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution.
* Neither the name of the ESN Social Software AB nor the
names of its contributors may be used to endorse or promote products
derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL ESN SOCIAL SOFTWARE AB OR JONAS TARNSTROM BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE
GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


Portions of code from MODP_ASCII - Ascii transformations (upper/lower, etc)
https://github.com/client9/stringencoders
Copyright (c) 2007  Nick Galbreath -- nickg [at] modp [dot] com. All rights
reserved.

Numeric decoder derived from from TCL library
http://www.opensource.apple.com/source/tcl/tcl-14/tcl/license.terms
* Copyright (c) 1988-1993 The Regents of the University of California.
* Copyright (c) 1994 Sun Microsystems, Inc.
*/
#define PY_ARRAY_UNIQUE_SYMBOL UJSON_NUMPY

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <numpy/arrayobject.h>
#include <numpy/arrayscalars.h>
#include <numpy/ndarraytypes.h>
#include <numpy/npy_math.h>
#include <ultrajson.h>
#include <../../../tslibs/src/datetime/np_datetime.h>
#include <../../../tslibs/src/datetime/np_datetime_strings.h>
#include "datetime.h"

static PyTypeObject *type_decimal;
static PyTypeObject *cls_dataframe;
static PyTypeObject *cls_series;
static PyTypeObject *cls_index;
static PyTypeObject *cls_nat;
PyObject *cls_timestamp;
PyObject *cls_timedelta;

npy_int64 get_nat(void) { return NPY_MIN_INT64; }

typedef void *(*PFN_PyTypeToJSON)(JSOBJ obj, JSONTypeContext *ti,
                                  void *outValue, size_t *_outLen);

typedef struct __NpyArrContext {
    PyObject *array;
    char *dataptr;
    int curdim;    // current dimension in array's order
    int stridedim; // dimension we are striding over
    int inc;       // stride dimension increment (+/- 1)
    npy_intp dim;
    npy_intp stride;
    npy_intp ndim;
    npy_intp index[NPY_MAXDIMS];
    int type_num;
    PyArray_GetItemFunc *getitem;

    char **rowLabels;
    char **columnLabels;
} NpyArrContext;

typedef struct __PdBlockContext {
    int colIdx;
    int ncols;
    int transpose;

    int *cindices;            // frame column -> block column map
    NpyArrContext **npyCtxts; // NpyArrContext for each column
} PdBlockContext;

typedef struct __TypeContext {
    JSPFN_ITERBEGIN iterBegin;
    JSPFN_ITEREND iterEnd;
    JSPFN_ITERNEXT iterNext;
    JSPFN_ITERGETNAME iterGetName;
    JSPFN_ITERGETVALUE iterGetValue;
    PFN_PyTypeToJSON PyTypeToJSON;
    PyObject *newObj;
    PyObject *dictObj;
    Py_ssize_t index;
    Py_ssize_t size;
    PyObject *itemValue;
    PyObject *itemName;
    PyObject *attrList;
    PyObject *iterator;

    double doubleValue;
    JSINT64 longValue;

    char *cStr;
    NpyArrContext *npyarr;
    PdBlockContext *pdblock;
    int transpose;
    char **rowLabels;
    char **columnLabels;
    npy_intp rowLabelsLen;
    npy_intp columnLabelsLen;
} TypeContext;

typedef struct __PyObjectEncoder {
    JSONObjectEncoder enc;

    // pass through the NpyArrContext when encoding multi-dimensional arrays
    NpyArrContext *npyCtxtPassthru;

    // pass through the PdBlockContext when encoding blocks
    PdBlockContext *blkCtxtPassthru;

    // pass-through to encode numpy data directly
    int npyType;
    void *npyValue;
    TypeContext basicTypeContext;

    int datetimeIso;
    NPY_DATETIMEUNIT datetimeUnit;

    // output format style for pandas data types
    int outputFormat;
    int originalOutputFormat;

    PyObject *defaultHandler;
} PyObjectEncoder;

#define GET_TC(__ptrtc) ((TypeContext *)((__ptrtc)->prv))

enum PANDAS_FORMAT { SPLIT, RECORDS, INDEX, COLUMNS, VALUES };

#define PRINTMARK()

int PdBlock_iterNext(JSOBJ, JSONTypeContext *);

void *initObjToJSON(void) {
    PyObject *mod_pandas;
    PyObject *mod_nattype;
    PyObject *mod_decimal = PyImport_ImportModule("decimal");
    type_decimal =
        (PyTypeObject *)PyObject_GetAttrString(mod_decimal, "Decimal");
    Py_DECREF(mod_decimal);

    PyDateTime_IMPORT;

    mod_pandas = PyImport_ImportModule("pandas");
    if (mod_pandas) {
        cls_dataframe =
            (PyTypeObject *)PyObject_GetAttrString(mod_pandas, "DataFrame");
        cls_index = (PyTypeObject *)PyObject_GetAttrString(mod_pandas, "Index");
        cls_series =
            (PyTypeObject *)PyObject_GetAttrString(mod_pandas, "Series");
        cls_timestamp = PyObject_GetAttrString(mod_pandas, "Timestamp");
        cls_timedelta = PyObject_GetAttrString(mod_pandas, "Timedelta");
        Py_DECREF(mod_pandas);
    }

    mod_nattype = PyImport_ImportModule("pandas._libs.tslibs.nattype");
    if (mod_nattype) {
        cls_nat =
            (PyTypeObject *)PyObject_GetAttrString(mod_nattype, "NaTType");
        Py_DECREF(mod_nattype);
    }

    /* Initialise numpy API and use 2/3 compatible return */
    import_array();
    return NUMPY_IMPORT_ARRAY_RETVAL;
}

static TypeContext *createTypeContext(void) {
    TypeContext *pc;

    pc = PyObject_Malloc(sizeof(TypeContext));
    if (!pc) {
        PyErr_NoMemory();
        return NULL;
    }
    pc->newObj = NULL;
    pc->dictObj = NULL;
    pc->itemValue = NULL;
    pc->itemName = NULL;
    pc->attrList = NULL;
    pc->index = 0;
    pc->size = 0;
    pc->longValue = 0;
    pc->doubleValue = 0.0;
    pc->cStr = NULL;
    pc->npyarr = NULL;
    pc->pdblock = NULL;
    pc->rowLabels = NULL;
    pc->columnLabels = NULL;
    pc->transpose = 0;
    pc->rowLabelsLen = 0;
    pc->columnLabelsLen = 0;

    return pc;
}

static int is_sparse_array(PyObject *obj) {
    // TODO can be removed again once SparseArray.values is removed (GH26421)
    if (PyObject_HasAttrString(obj, "_subtyp")) {
        PyObject *_subtype = PyObject_GetAttrString(obj, "_subtyp");
        PyObject *sparse_array = PyUnicode_FromString("sparse_array");
        int ret = PyUnicode_Compare(_subtype, sparse_array);

        if (ret == 0) {
            return 1;
        }
    }
    return 0;
}

static PyObject *get_values(PyObject *obj) {
    PyObject *values = NULL;

    if (!is_sparse_array(obj)) {
        values = PyObject_GetAttrString(obj, "values");
        PRINTMARK();
    }

    if (values && !PyArray_CheckExact(values)) {

        if (PyObject_HasAttrString(values, "to_numpy")) {
            values = PyObject_CallMethod(values, "to_numpy", NULL);
        }

        if (!is_sparse_array(values) &&
            PyObject_HasAttrString(values, "values")) {
            PyObject *subvals = get_values(values);
            PyErr_Clear();
            PRINTMARK();
            // subvals are sometimes missing a dimension
            if (subvals) {
                PyArrayObject *reshape = (PyArrayObject *)subvals;
                PyObject *shape = PyObject_GetAttrString(obj, "shape");
                PyArray_Dims dims;
                PRINTMARK();

                if (!shape || !PyArray_IntpConverter(shape, &dims)) {
                    subvals = NULL;
                } else {
                    subvals = PyArray_Newshape(reshape, &dims, NPY_ANYORDER);
                    PyDimMem_FREE(dims.ptr);
                }
                Py_DECREF(reshape);
                Py_XDECREF(shape);
            }
            Py_DECREF(values);
            values = subvals;
        } else {
            PRINTMARK();
            Py_DECREF(values);
            values = NULL;
        }
    }

    if (!values && PyObject_HasAttrString(obj, "_internal_get_values")) {
        PRINTMARK();
        values = PyObject_CallMethod(obj, "_internal_get_values", NULL);
        if (values && !PyArray_CheckExact(values)) {
            PRINTMARK();
            Py_DECREF(values);
            values = NULL;
        }
    }

    if (!values && PyObject_HasAttrString(obj, "get_block_values")) {
        PRINTMARK();
        values = PyObject_CallMethod(obj, "get_block_values", NULL);
        if (values && !PyArray_CheckExact(values)) {
            PRINTMARK();
            Py_DECREF(values);
            values = NULL;
        }
    }

    if (!values) {
        PyObject *typeRepr = PyObject_Repr((PyObject *)Py_TYPE(obj));
        PyObject *repr;
        PRINTMARK();
        if (PyObject_HasAttrString(obj, "dtype")) {
            PyObject *dtype = PyObject_GetAttrString(obj, "dtype");
            repr = PyObject_Repr(dtype);
            Py_DECREF(dtype);
        } else {
            repr = PyUnicode_FromString("<unknown dtype>");
        }

        PyErr_Format(PyExc_ValueError, "%R or %R are not JSON serializable yet",
                     repr, typeRepr);
        Py_DECREF(repr);
        Py_DECREF(typeRepr);

        return NULL;
    }

    return values;
}

static PyObject *get_sub_attr(PyObject *obj, char *attr, char *subAttr) {
    PyObject *tmp = PyObject_GetAttrString(obj, attr);
    PyObject *ret;

    if (tmp == 0) {
        return 0;
    }
    ret = PyObject_GetAttrString(tmp, subAttr);
    Py_DECREF(tmp);

    return ret;
}

static int is_simple_frame(PyObject *obj) {
    PyObject *check = get_sub_attr(obj, "_data", "is_mixed_type");
    int ret = (check == Py_False);

    if (!check) {
        return 0;
    }

    Py_DECREF(check);
    return ret;
}

static Py_ssize_t get_attr_length(PyObject *obj, char *attr) {
    PyObject *tmp = PyObject_GetAttrString(obj, attr);
    Py_ssize_t ret;

    if (tmp == 0) {
        return 0;
    }
    ret = PyObject_Length(tmp);
    Py_DECREF(tmp);

    if (ret == -1) {
        return 0;
    }

    return ret;
}

static npy_int64 get_long_attr(PyObject *o, const char *attr) {
    npy_int64 long_val;
    PyObject *value = PyObject_GetAttrString(o, attr);
    long_val =
        (PyLong_Check(value) ? PyLong_AsLongLong(value) : PyLong_AsLong(value));
    Py_DECREF(value);
    return long_val;
}

static npy_float64 total_seconds(PyObject *td) {
    npy_float64 double_val;
    PyObject *value = PyObject_CallMethod(td, "total_seconds", NULL);
    double_val = PyFloat_AS_DOUBLE(value);
    Py_DECREF(value);
    return double_val;
}

static PyObject *get_item(PyObject *obj, Py_ssize_t i) {
    PyObject *tmp = PyLong_FromSsize_t(i);
    PyObject *ret;

    if (tmp == 0) {
        return 0;
    }
    ret = PyObject_GetItem(obj, tmp);
    Py_DECREF(tmp);

    return ret;
}

static void *PyBytesToUTF8(JSOBJ _obj, JSONTypeContext *tc, void *outValue,
                           size_t *_outLen) {
    PyObject *obj = (PyObject *)_obj;
    *_outLen = PyBytes_GET_SIZE(obj);
    return PyBytes_AS_STRING(obj);
}

static void *PyUnicodeToUTF8(JSOBJ _obj, JSONTypeContext *tc, void *outValue,
                             size_t *_outLen) {
    PyObject *obj, *newObj;
    obj = (PyObject *)_obj;

    if (PyUnicode_IS_COMPACT_ASCII(obj)) {
        Py_ssize_t len;
        char *data = (char *)PyUnicode_AsUTF8AndSize(obj, &len);
        *_outLen = len;
        return data;
    }

    newObj = PyUnicode_AsUTF8String(obj);

    GET_TC(tc)->newObj = newObj;

    *_outLen = PyBytes_GET_SIZE(newObj);
    return PyBytes_AS_STRING(newObj);
}

static void *PandasDateTimeStructToJSON(npy_datetimestruct *dts,
                                        JSONTypeContext *tc, void *outValue,
                                        size_t *_outLen) {
    NPY_DATETIMEUNIT base = ((PyObjectEncoder *)tc->encoder)->datetimeUnit;

    if (((PyObjectEncoder *)tc->encoder)->datetimeIso) {
        PRINTMARK();
        *_outLen = (size_t)get_datetime_iso_8601_strlen(0, base);
        GET_TC(tc)->cStr = PyObject_Malloc(sizeof(char) * (*_outLen));
        if (!GET_TC(tc)->cStr) {
            PyErr_NoMemory();
            ((JSONObjectEncoder *)tc->encoder)->errorMsg = "";
            return NULL;
        }

        if (!make_iso_8601_datetime(dts, GET_TC(tc)->cStr, *_outLen, base)) {
            PRINTMARK();
            *_outLen = strlen(GET_TC(tc)->cStr);
            return GET_TC(tc)->cStr;
        } else {
            PRINTMARK();
            PyErr_SetString(PyExc_ValueError,
                            "Could not convert datetime value to string");
            ((JSONObjectEncoder *)tc->encoder)->errorMsg = "";
            PyObject_Free(GET_TC(tc)->cStr);
            return NULL;
        }
    } else {
        PRINTMARK();
        *((JSINT64 *)outValue) = npy_datetimestruct_to_datetime(base, dts);
        return NULL;
    }
}

static void *NpyDateTimeScalarToJSON(JSOBJ _obj, JSONTypeContext *tc,
                                     void *outValue, size_t *_outLen) {
    npy_datetimestruct dts;
    PyDatetimeScalarObject *obj = (PyDatetimeScalarObject *)_obj;
    PRINTMARK();
    // TODO(anyone): Does not appear to be reached in tests.

    pandas_datetime_to_datetimestruct(obj->obval,
                                      (NPY_DATETIMEUNIT)obj->obmeta.base, &dts);
    return PandasDateTimeStructToJSON(&dts, tc, outValue, _outLen);
}

static void *PyDateTimeToJSON(JSOBJ _obj, JSONTypeContext *tc, void *outValue,
                              size_t *_outLen) {
    npy_datetimestruct dts;
    PyDateTime_Date *obj = (PyDateTime_Date *)_obj;

    PRINTMARK();

    if (!convert_pydatetime_to_datetimestruct(obj, &dts)) {
        PRINTMARK();
        return PandasDateTimeStructToJSON(&dts, tc, outValue, _outLen);
    } else {
        if (!PyErr_Occurred()) {
            PyErr_SetString(PyExc_ValueError,
                            "Could not convert datetime value to string");
        }
        ((JSONObjectEncoder *)tc->encoder)->errorMsg = "";
        return NULL;
    }
}

static void *NpyDatetime64ToJSON(JSOBJ _obj, JSONTypeContext *tc,
                                 void *outValue, size_t *_outLen) {
    npy_datetimestruct dts;
    PRINTMARK();

    pandas_datetime_to_datetimestruct((npy_datetime)GET_TC(tc)->longValue,
                                      NPY_FR_ns, &dts);
    return PandasDateTimeStructToJSON(&dts, tc, outValue, _outLen);
}

static void *PyTimeToJSON(JSOBJ _obj, JSONTypeContext *tc, void *outValue,
                          size_t *outLen) {
    PyObject *obj = (PyObject *)_obj;
    PyObject *str;
    PyObject *tmp;

    str = PyObject_CallMethod(obj, "isoformat", NULL);
    if (str == NULL) {
        PRINTMARK();
        *outLen = 0;
        if (!PyErr_Occurred()) {
            PyErr_SetString(PyExc_ValueError, "Failed to convert time");
        }
        ((JSONObjectEncoder *)tc->encoder)->errorMsg = "";
        return NULL;
    }
    if (PyUnicode_Check(str)) {
        tmp = str;
        str = PyUnicode_AsUTF8String(str);
        Py_DECREF(tmp);
    }

    GET_TC(tc)->newObj = str;

    *outLen = PyBytes_GET_SIZE(str);
    outValue = (void *)PyBytes_AS_STRING(str);
    return outValue;
}

static int NpyTypeToJSONType(PyObject *obj, JSONTypeContext *tc, int npyType,
                             void *value) {
    PyArray_VectorUnaryFunc *castfunc;
    npy_double doubleVal;
    npy_int64 longVal;

    if (PyTypeNum_ISFLOAT(npyType)) {
        PRINTMARK();
        castfunc =
            PyArray_GetCastFunc(PyArray_DescrFromType(npyType), NPY_DOUBLE);
        if (!castfunc) {
            PyErr_Format(PyExc_ValueError,
                         "Cannot cast numpy dtype %d to double", npyType);
        }
        castfunc(value, &doubleVal, 1, NULL, NULL);
        if (npy_isnan(doubleVal) || npy_isinf(doubleVal)) {
            PRINTMARK();
            return JT_NULL;
        }
        GET_TC(tc)->doubleValue = (double)doubleVal;
        return JT_DOUBLE;
    }

    if (PyTypeNum_ISDATETIME(npyType)) {
        PRINTMARK();
        castfunc =
            PyArray_GetCastFunc(PyArray_DescrFromType(npyType), NPY_INT64);
        if (!castfunc) {
            PyErr_Format(PyExc_ValueError, "Cannot cast numpy dtype %d to long",
                         npyType);
        }
        castfunc(value, &longVal, 1, NULL, NULL);
        if (longVal == get_nat()) {
            PRINTMARK();
            return JT_NULL;
        }

        if (((PyObjectEncoder *)tc->encoder)->datetimeIso) {
            GET_TC(tc)->longValue = (JSINT64)longVal;
            GET_TC(tc)->PyTypeToJSON = NpyDatetime64ToJSON;
            return JT_UTF8;
        } else {

            // TODO: consolidate uses of this switch
            switch (((PyObjectEncoder *)tc->encoder)->datetimeUnit) {
            case NPY_FR_ns:
                break;
            case NPY_FR_us:
                longVal /= 1000LL;
                break;
            case NPY_FR_ms:
                longVal /= 1000000LL;
                break;
            case NPY_FR_s:
                longVal /= 1000000000LL;
                break;
            default:
                break; // TODO: should raise error
            }
            GET_TC(tc)->longValue = longVal;
            return JT_LONG;
        }
    }

    if (PyTypeNum_ISINTEGER(npyType)) {
        PRINTMARK();
        castfunc =
            PyArray_GetCastFunc(PyArray_DescrFromType(npyType), NPY_INT64);
        if (!castfunc) {
            PyErr_Format(PyExc_ValueError, "Cannot cast numpy dtype %d to long",
                         npyType);
        }
        castfunc(value, &longVal, 1, NULL, NULL);
        GET_TC(tc)->longValue = (JSINT64)longVal;
        return JT_LONG;
    }

    if (PyTypeNum_ISBOOL(npyType)) {
        PRINTMARK();
        return *((npy_bool *)value) == NPY_TRUE ? JT_TRUE : JT_FALSE;
    }

    PRINTMARK();
    return JT_INVALID;
}

//=============================================================================
// Numpy array iteration functions
//=============================================================================

static void NpyArr_freeItemValue(JSOBJ _obj, JSONTypeContext *tc) {
    if (GET_TC(tc)->npyarr &&
        GET_TC(tc)->itemValue != GET_TC(tc)->npyarr->array) {
        PRINTMARK();
        Py_XDECREF(GET_TC(tc)->itemValue);
        GET_TC(tc)->itemValue = NULL;
    }
}

int NpyArr_iterNextNone(JSOBJ _obj, JSONTypeContext *tc) { return 0; }

void NpyArr_iterBegin(JSOBJ _obj, JSONTypeContext *tc) {
    PyArrayObject *obj;
    NpyArrContext *npyarr;

    if (GET_TC(tc)->newObj) {
        obj = (PyArrayObject *)GET_TC(tc)->newObj;
    } else {
        obj = (PyArrayObject *)_obj;
    }

    PRINTMARK();
    npyarr = PyObject_Malloc(sizeof(NpyArrContext));
    GET_TC(tc)->npyarr = npyarr;

    if (!npyarr) {
        PyErr_NoMemory();
        GET_TC(tc)->iterNext = NpyArr_iterNextNone;
        return;
    }

    npyarr->array = (PyObject *)obj;
    npyarr->getitem = (PyArray_GetItemFunc *)PyArray_DESCR(obj)->f->getitem;
    npyarr->dataptr = PyArray_DATA(obj);
    npyarr->ndim = PyArray_NDIM(obj) - 1;
    npyarr->curdim = 0;
    npyarr->type_num = PyArray_DESCR(obj)->type_num;

    if (GET_TC(tc)->transpose) {
        npyarr->dim = PyArray_DIM(obj, npyarr->ndim);
        npyarr->stride = PyArray_STRIDE(obj, npyarr->ndim);
        npyarr->stridedim = npyarr->ndim;
        npyarr->index[npyarr->ndim] = 0;
        npyarr->inc = -1;
    } else {
        npyarr->dim = PyArray_DIM(obj, 0);
        npyarr->stride = PyArray_STRIDE(obj, 0);
        npyarr->stridedim = 0;
        npyarr->index[0] = 0;
        npyarr->inc = 1;
    }

    npyarr->columnLabels = GET_TC(tc)->columnLabels;
    npyarr->rowLabels = GET_TC(tc)->rowLabels;
}

void NpyArr_iterEnd(JSOBJ obj, JSONTypeContext *tc) {
    NpyArrContext *npyarr = GET_TC(tc)->npyarr;
    PRINTMARK();

    if (npyarr) {
        NpyArr_freeItemValue(obj, tc);
        PyObject_Free(npyarr);
    }
}

void NpyArrPassThru_iterBegin(JSOBJ obj, JSONTypeContext *tc) { PRINTMARK(); }

void NpyArrPassThru_iterEnd(JSOBJ obj, JSONTypeContext *tc) {
    NpyArrContext *npyarr = GET_TC(tc)->npyarr;
    PRINTMARK();
    // finished this dimension, reset the data pointer
    npyarr->curdim--;
    npyarr->dataptr -= npyarr->stride * npyarr->index[npyarr->stridedim];
    npyarr->stridedim -= npyarr->inc;
    npyarr->dim = PyArray_DIM(npyarr->array, npyarr->stridedim);
    npyarr->stride = PyArray_STRIDE(npyarr->array, npyarr->stridedim);
    npyarr->dataptr += npyarr->stride;

    NpyArr_freeItemValue(obj, tc);
}

int NpyArr_iterNextItem(JSOBJ obj, JSONTypeContext *tc) {
    NpyArrContext *npyarr = GET_TC(tc)->npyarr;
    PRINTMARK();

    if (PyErr_Occurred()) {
        return 0;
    }

    if (npyarr->index[npyarr->stridedim] >= npyarr->dim) {
        PRINTMARK();
        return 0;
    }

    NpyArr_freeItemValue(obj, tc);

    if (PyArray_ISDATETIME(npyarr->array)) {
        PRINTMARK();
        GET_TC(tc)->itemValue = obj;
        Py_INCREF(obj);
        ((PyObjectEncoder *)tc->encoder)->npyType = PyArray_TYPE(npyarr->array);
        ((PyObjectEncoder *)tc->encoder)->npyValue = npyarr->dataptr;
        ((PyObjectEncoder *)tc->encoder)->npyCtxtPassthru = npyarr;
    } else {
        PRINTMARK();
        GET_TC(tc)->itemValue = npyarr->getitem(npyarr->dataptr, npyarr->array);
    }

    npyarr->dataptr += npyarr->stride;
    npyarr->index[npyarr->stridedim]++;
    return 1;
}

int NpyArr_iterNext(JSOBJ _obj, JSONTypeContext *tc) {
    NpyArrContext *npyarr = GET_TC(tc)->npyarr;
    PRINTMARK();

    if (PyErr_Occurred()) {
        PRINTMARK();
        return 0;
    }

    if (npyarr->curdim >= npyarr->ndim ||
        npyarr->index[npyarr->stridedim] >= npyarr->dim) {
        PRINTMARK();
        // innermost dimension, start retrieving item values
        GET_TC(tc)->iterNext = NpyArr_iterNextItem;
        return NpyArr_iterNextItem(_obj, tc);
    }

    // dig a dimension deeper
    npyarr->index[npyarr->stridedim]++;

    npyarr->curdim++;
    npyarr->stridedim += npyarr->inc;
    npyarr->dim = PyArray_DIM(npyarr->array, npyarr->stridedim);
    npyarr->stride = PyArray_STRIDE(npyarr->array, npyarr->stridedim);
    npyarr->index[npyarr->stridedim] = 0;

    ((PyObjectEncoder *)tc->encoder)->npyCtxtPassthru = npyarr;
    GET_TC(tc)->itemValue = npyarr->array;
    return 1;
}

JSOBJ NpyArr_iterGetValue(JSOBJ obj, JSONTypeContext *tc) {
    PRINTMARK();
    return GET_TC(tc)->itemValue;
}

char *NpyArr_iterGetName(JSOBJ obj, JSONTypeContext *tc, size_t *outLen) {
    NpyArrContext *npyarr = GET_TC(tc)->npyarr;
    npy_intp idx;
    PRINTMARK();
    char *cStr;

    if (GET_TC(tc)->iterNext == NpyArr_iterNextItem) {
        idx = npyarr->index[npyarr->stridedim] - 1;
        cStr = npyarr->columnLabels[idx];
    } else {
        idx = npyarr->index[npyarr->stridedim - npyarr->inc] - 1;
        cStr = npyarr->rowLabels[idx];
    }

    *outLen = strlen(cStr);

    return cStr;
}

//=============================================================================
// Pandas block iteration functions
//
// Serialises a DataFrame column by column to avoid unnecessary data copies and
// more representative serialisation when dealing with mixed dtypes.
//
// Uses a dedicated NpyArrContext for each column.
//=============================================================================

void PdBlockPassThru_iterEnd(JSOBJ obj, JSONTypeContext *tc) {
    PdBlockContext *blkCtxt = GET_TC(tc)->pdblock;
    PRINTMARK();

    if (blkCtxt->transpose) {
        blkCtxt->colIdx++;
    } else {
        blkCtxt->colIdx = 0;
    }

    NpyArr_freeItemValue(obj, tc);
}

int PdBlock_iterNextItem(JSOBJ obj, JSONTypeContext *tc) {
    PdBlockContext *blkCtxt = GET_TC(tc)->pdblock;
    PRINTMARK();

    if (blkCtxt->colIdx >= blkCtxt->ncols) {
        return 0;
    }

    GET_TC(tc)->npyarr = blkCtxt->npyCtxts[blkCtxt->colIdx];
    blkCtxt->colIdx++;
    return NpyArr_iterNextItem(obj, tc);
}

char *PdBlock_iterGetName(JSOBJ obj, JSONTypeContext *tc, size_t *outLen) {
    PdBlockContext *blkCtxt = GET_TC(tc)->pdblock;
    NpyArrContext *npyarr = blkCtxt->npyCtxts[0];
    npy_intp idx;
    char *cStr;
    PRINTMARK();

    if (GET_TC(tc)->iterNext == PdBlock_iterNextItem) {
        idx = blkCtxt->colIdx - 1;
        cStr = npyarr->columnLabels[idx];
    } else {
        idx = GET_TC(tc)->iterNext != PdBlock_iterNext
                  ? npyarr->index[npyarr->stridedim - npyarr->inc] - 1
                  : npyarr->index[npyarr->stridedim];

        cStr = npyarr->rowLabels[idx];
    }

    *outLen = strlen(cStr);
    return cStr;
}

char *PdBlock_iterGetName_Transpose(JSOBJ obj, JSONTypeContext *tc,
                                    size_t *outLen) {
    PdBlockContext *blkCtxt = GET_TC(tc)->pdblock;
    NpyArrContext *npyarr = blkCtxt->npyCtxts[blkCtxt->colIdx];
    npy_intp idx;
    char *cStr;
    PRINTMARK();

    if (GET_TC(tc)->iterNext == NpyArr_iterNextItem) {
        idx = npyarr->index[npyarr->stridedim] - 1;
        cStr = npyarr->columnLabels[idx];
    } else {
        idx = blkCtxt->colIdx;
        cStr = npyarr->rowLabels[idx];
    }

    *outLen = strlen(cStr);
    return cStr;
}

int PdBlock_iterNext(JSOBJ obj, JSONTypeContext *tc) {
    PdBlockContext *blkCtxt = GET_TC(tc)->pdblock;
    NpyArrContext *npyarr;
    PRINTMARK();

    if (PyErr_Occurred() || ((JSONObjectEncoder *)tc->encoder)->errorMsg) {
        return 0;
    }

    if (blkCtxt->transpose) {
        if (blkCtxt->colIdx >= blkCtxt->ncols) {
            return 0;
        }
    } else {
        npyarr = blkCtxt->npyCtxts[0];
        if (npyarr->index[npyarr->stridedim] >= npyarr->dim) {
            return 0;
        }
    }

    ((PyObjectEncoder *)tc->encoder)->blkCtxtPassthru = blkCtxt;
    GET_TC(tc)->itemValue = obj;

    return 1;
}

void PdBlockPassThru_iterBegin(JSOBJ obj, JSONTypeContext *tc) {
    PdBlockContext *blkCtxt = GET_TC(tc)->pdblock;
    PRINTMARK();

    if (blkCtxt->transpose) {
        // if transposed we exhaust each column before moving to the next
        GET_TC(tc)->iterNext = NpyArr_iterNextItem;
        GET_TC(tc)->iterGetName = PdBlock_iterGetName_Transpose;
        GET_TC(tc)->npyarr = blkCtxt->npyCtxts[blkCtxt->colIdx];
    }
}

void PdBlock_iterBegin(JSOBJ _obj, JSONTypeContext *tc) {
    PyObject *obj, *blocks, *block, *values, *tmp;
    PyArrayObject *locs;
    PdBlockContext *blkCtxt;
    NpyArrContext *npyarr;
    Py_ssize_t i;
    PyArray_Descr *dtype;
    NpyIter *iter;
    NpyIter_IterNextFunc *iternext;
    npy_int64 **dataptr;
    npy_int64 colIdx;
    npy_intp idx;

    PRINTMARK();

    i = 0;
    blocks = NULL;
    dtype = PyArray_DescrFromType(NPY_INT64);
    obj = (PyObject *)_obj;

    GET_TC(tc)->iterGetName = GET_TC(tc)->transpose
                                  ? PdBlock_iterGetName_Transpose
                                  : PdBlock_iterGetName;

    blkCtxt = PyObject_Malloc(sizeof(PdBlockContext));
    if (!blkCtxt) {
        PyErr_NoMemory();
        GET_TC(tc)->iterNext = NpyArr_iterNextNone;
        goto BLKRET;
    }
    GET_TC(tc)->pdblock = blkCtxt;

    blkCtxt->colIdx = 0;
    blkCtxt->transpose = GET_TC(tc)->transpose;
    blkCtxt->ncols = get_attr_length(obj, "columns");

    if (blkCtxt->ncols == 0) {
        blkCtxt->npyCtxts = NULL;
        blkCtxt->cindices = NULL;

        GET_TC(tc)->iterNext = NpyArr_iterNextNone;
        goto BLKRET;
    }

    blkCtxt->npyCtxts =
        PyObject_Malloc(sizeof(NpyArrContext *) * blkCtxt->ncols);
    if (!blkCtxt->npyCtxts) {
        PyErr_NoMemory();
        GET_TC(tc)->iterNext = NpyArr_iterNextNone;
        goto BLKRET;
    }
    for (i = 0; i < blkCtxt->ncols; i++) {
        blkCtxt->npyCtxts[i] = NULL;
    }

    blkCtxt->cindices = PyObject_Malloc(sizeof(int) * blkCtxt->ncols);
    if (!blkCtxt->cindices) {
        PyErr_NoMemory();
        GET_TC(tc)->iterNext = NpyArr_iterNextNone;
        goto BLKRET;
    }

    blocks = get_sub_attr(obj, "_data", "blocks");
    if (!blocks) {
        GET_TC(tc)->iterNext = NpyArr_iterNextNone;
        goto BLKRET;
    }

    // force transpose so each NpyArrContext strides down its column
    GET_TC(tc)->transpose = 1;

    for (i = 0; i < PyObject_Length(blocks); i++) {
        block = get_item(blocks, i);
        if (!block) {
            GET_TC(tc)->iterNext = NpyArr_iterNextNone;
            goto BLKRET;
        }

        tmp = get_values(block);
        if (!tmp) {
            ((JSONObjectEncoder *)tc->encoder)->errorMsg = "";
            Py_DECREF(block);
            GET_TC(tc)->iterNext = NpyArr_iterNextNone;
            goto BLKRET;
        }

        values = PyArray_Transpose((PyArrayObject *)tmp, NULL);
        Py_DECREF(tmp);
        if (!values) {
            Py_DECREF(block);
            GET_TC(tc)->iterNext = NpyArr_iterNextNone;
            goto BLKRET;
        }

        locs = (PyArrayObject *)get_sub_attr(block, "mgr_locs", "as_array");
        if (!locs) {
            Py_DECREF(block);
            Py_DECREF(values);
            GET_TC(tc)->iterNext = NpyArr_iterNextNone;
            goto BLKRET;
        }

        iter = NpyIter_New(locs, NPY_ITER_READONLY, NPY_KEEPORDER,
                           NPY_NO_CASTING, dtype);
        if (!iter) {
            Py_DECREF(block);
            Py_DECREF(values);
            Py_DECREF(locs);
            GET_TC(tc)->iterNext = NpyArr_iterNextNone;
            goto BLKRET;
        }
        iternext = NpyIter_GetIterNext(iter, NULL);
        if (!iternext) {
            NpyIter_Deallocate(iter);
            Py_DECREF(block);
            Py_DECREF(values);
            Py_DECREF(locs);
            GET_TC(tc)->iterNext = NpyArr_iterNextNone;
            goto BLKRET;
        }
        dataptr = (npy_int64 **)NpyIter_GetDataPtrArray(iter);
        do {
            colIdx = **dataptr;
            idx = NpyIter_GetIterIndex(iter);

            blkCtxt->cindices[colIdx] = idx;

            // Reference freed in Pdblock_iterend
            Py_INCREF(values);
            GET_TC(tc)->newObj = values;

            // init a dedicated context for this column
            NpyArr_iterBegin(obj, tc);
            npyarr = GET_TC(tc)->npyarr;

            // set the dataptr to our desired column and initialise
            if (npyarr != NULL) {
                npyarr->dataptr += npyarr->stride * idx;
                NpyArr_iterNext(obj, tc);
            }
            GET_TC(tc)->itemValue = NULL;
            ((PyObjectEncoder *)tc->encoder)->npyCtxtPassthru = NULL;

            blkCtxt->npyCtxts[colIdx] = npyarr;
            GET_TC(tc)->newObj = NULL;
        } while (iternext(iter));

        NpyIter_Deallocate(iter);
        Py_DECREF(block);
        Py_DECREF(values);
        Py_DECREF(locs);
    }
    GET_TC(tc)->npyarr = blkCtxt->npyCtxts[0];

BLKRET:
    Py_XDECREF(dtype);
    Py_XDECREF(blocks);
}

void PdBlock_iterEnd(JSOBJ obj, JSONTypeContext *tc) {
    PdBlockContext *blkCtxt;
    NpyArrContext *npyarr;
    int i;
    PRINTMARK();

    GET_TC(tc)->itemValue = NULL;
    npyarr = GET_TC(tc)->npyarr;

    blkCtxt = GET_TC(tc)->pdblock;

    if (blkCtxt) {
        for (i = 0; i < blkCtxt->ncols; i++) {
            npyarr = blkCtxt->npyCtxts[i];
            if (npyarr) {
                if (npyarr->array) {
                    Py_DECREF(npyarr->array);
                    npyarr->array = NULL;
                }

                GET_TC(tc)->npyarr = npyarr;
                NpyArr_iterEnd(obj, tc);

                blkCtxt->npyCtxts[i] = NULL;
            }
        }

        if (blkCtxt->npyCtxts) {
            PyObject_Free(blkCtxt->npyCtxts);
        }
        if (blkCtxt->cindices) {
            PyObject_Free(blkCtxt->cindices);
        }
        PyObject_Free(blkCtxt);
    }
}

//=============================================================================
// Tuple iteration functions
// itemValue is borrowed reference, no ref counting
//=============================================================================
void Tuple_iterBegin(JSOBJ obj, JSONTypeContext *tc) {
    GET_TC(tc)->index = 0;
    GET_TC(tc)->size = PyTuple_GET_SIZE((PyObject *)obj);
    GET_TC(tc)->itemValue = NULL;
}

int Tuple_iterNext(JSOBJ obj, JSONTypeContext *tc) {
    PyObject *item;

    if (GET_TC(tc)->index >= GET_TC(tc)->size) {
        return 0;
    }

    item = PyTuple_GET_ITEM(obj, GET_TC(tc)->index);

    GET_TC(tc)->itemValue = item;
    GET_TC(tc)->index++;
    return 1;
}

void Tuple_iterEnd(JSOBJ obj, JSONTypeContext *tc) {}

JSOBJ Tuple_iterGetValue(JSOBJ obj, JSONTypeContext *tc) {
    return GET_TC(tc)->itemValue;
}

char *Tuple_iterGetName(JSOBJ obj, JSONTypeContext *tc, size_t *outLen) {
    return NULL;
}

//=============================================================================
// Iterator iteration functions
// itemValue is borrowed reference, no ref counting
//=============================================================================
void Iter_iterBegin(JSOBJ obj, JSONTypeContext *tc) {
    GET_TC(tc)->itemValue = NULL;
    GET_TC(tc)->iterator = PyObject_GetIter(obj);
}

int Iter_iterNext(JSOBJ obj, JSONTypeContext *tc) {
    PyObject *item;

    if (GET_TC(tc)->itemValue) {
        Py_DECREF(GET_TC(tc)->itemValue);
        GET_TC(tc)->itemValue = NULL;
    }

    item = PyIter_Next(GET_TC(tc)->iterator);

    if (item == NULL) {
        return 0;
    }

    GET_TC(tc)->itemValue = item;
    return 1;
}

void Iter_iterEnd(JSOBJ obj, JSONTypeContext *tc) {
    if (GET_TC(tc)->itemValue) {
        Py_DECREF(GET_TC(tc)->itemValue);
        GET_TC(tc)->itemValue = NULL;
    }

    if (GET_TC(tc)->iterator) {
        Py_DECREF(GET_TC(tc)->iterator);
        GET_TC(tc)->iterator = NULL;
    }
}

JSOBJ Iter_iterGetValue(JSOBJ obj, JSONTypeContext *tc) {
    return GET_TC(tc)->itemValue;
}

char *Iter_iterGetName(JSOBJ obj, JSONTypeContext *tc, size_t *outLen) {
    return NULL;
}

//=============================================================================
// Dir iteration functions
// itemName ref is borrowed from PyObject_Dir (attrList). No refcount
// itemValue ref is from PyObject_GetAttr. Ref counted
//=============================================================================
void Dir_iterBegin(JSOBJ obj, JSONTypeContext *tc) {
    GET_TC(tc)->attrList = PyObject_Dir(obj);
    GET_TC(tc)->index = 0;
    GET_TC(tc)->size = PyList_GET_SIZE(GET_TC(tc)->attrList);
    PRINTMARK();
}

void Dir_iterEnd(JSOBJ obj, JSONTypeContext *tc) {
    if (GET_TC(tc)->itemValue) {
        Py_DECREF(GET_TC(tc)->itemValue);
        GET_TC(tc)->itemValue = NULL;
    }

    if (GET_TC(tc)->itemName) {
        Py_DECREF(GET_TC(tc)->itemName);
        GET_TC(tc)->itemName = NULL;
    }

    Py_DECREF((PyObject *)GET_TC(tc)->attrList);
    PRINTMARK();
}

int Dir_iterNext(JSOBJ _obj, JSONTypeContext *tc) {
    PyObject *obj = (PyObject *)_obj;
    PyObject *itemValue = GET_TC(tc)->itemValue;
    PyObject *itemName = GET_TC(tc)->itemName;
    PyObject *attr;
    PyObject *attrName;
    char *attrStr;

    if (PyErr_Occurred() || ((JSONObjectEncoder *)tc->encoder)->errorMsg) {
        return 0;
    }

    if (itemValue) {
        Py_DECREF(GET_TC(tc)->itemValue);
        GET_TC(tc)->itemValue = itemValue = NULL;
    }

    if (itemName) {
        Py_DECREF(GET_TC(tc)->itemName);
        GET_TC(tc)->itemName = itemName = NULL;
    }

    for (; GET_TC(tc)->index < GET_TC(tc)->size; GET_TC(tc)->index++) {
        attrName = PyList_GET_ITEM(GET_TC(tc)->attrList, GET_TC(tc)->index);
        attr = PyUnicode_AsUTF8String(attrName);
        attrStr = PyBytes_AS_STRING(attr);

        if (attrStr[0] == '_') {
            PRINTMARK();
            Py_DECREF(attr);
            continue;
        }

        itemValue = PyObject_GetAttr(obj, attrName);
        if (itemValue == NULL) {
            PyErr_Clear();
            Py_DECREF(attr);
            PRINTMARK();
            continue;
        }

        if (PyCallable_Check(itemValue)) {
            Py_DECREF(itemValue);
            Py_DECREF(attr);
            PRINTMARK();
            continue;
        }

        GET_TC(tc)->itemName = itemName;
        GET_TC(tc)->itemValue = itemValue;
        GET_TC(tc)->index++;

        PRINTMARK();
        itemName = attr;
        break;
    }

    if (itemName == NULL) {
        GET_TC(tc)->index = GET_TC(tc)->size;
        GET_TC(tc)->itemValue = NULL;
        return 0;
    }

    GET_TC(tc)->itemName = itemName;
    GET_TC(tc)->itemValue = itemValue;
    GET_TC(tc)->index++;

    PRINTMARK();
    return 1;
}

JSOBJ Dir_iterGetValue(JSOBJ obj, JSONTypeContext *tc) {
    PRINTMARK();
    return GET_TC(tc)->itemValue;
}

char *Dir_iterGetName(JSOBJ obj, JSONTypeContext *tc, size_t *outLen) {
    PRINTMARK();
    *outLen = PyBytes_GET_SIZE(GET_TC(tc)->itemName);
    return PyBytes_AS_STRING(GET_TC(tc)->itemName);
}

//=============================================================================
// List iteration functions
// itemValue is borrowed from object (which is list). No refcounting
//=============================================================================
void List_iterBegin(JSOBJ obj, JSONTypeContext *tc) {
    GET_TC(tc)->index = 0;
    GET_TC(tc)->size = PyList_GET_SIZE((PyObject *)obj);
}

int List_iterNext(JSOBJ obj, JSONTypeContext *tc) {
    if (GET_TC(tc)->index >= GET_TC(tc)->size) {
        PRINTMARK();
        return 0;
    }

    GET_TC(tc)->itemValue = PyList_GET_ITEM(obj, GET_TC(tc)->index);
    GET_TC(tc)->index++;
    return 1;
}

void List_iterEnd(JSOBJ obj, JSONTypeContext *tc) {}

JSOBJ List_iterGetValue(JSOBJ obj, JSONTypeContext *tc) {
    return GET_TC(tc)->itemValue;
}

char *List_iterGetName(JSOBJ obj, JSONTypeContext *tc, size_t *outLen) {
    return NULL;
}

//=============================================================================
// pandas Index iteration functions
//=============================================================================
void Index_iterBegin(JSOBJ obj, JSONTypeContext *tc) {
    GET_TC(tc)->index = 0;
    GET_TC(tc)->cStr = PyObject_Malloc(20 * sizeof(char));
    if (!GET_TC(tc)->cStr) {
        PyErr_NoMemory();
    }
    PRINTMARK();
}

int Index_iterNext(JSOBJ obj, JSONTypeContext *tc) {
    Py_ssize_t index;
    if (!GET_TC(tc)->cStr) {
        return 0;
    }

    index = GET_TC(tc)->index;
    Py_XDECREF(GET_TC(tc)->itemValue);
    if (index == 0) {
        memcpy(GET_TC(tc)->cStr, "name", sizeof(char) * 5);
        GET_TC(tc)->itemValue = PyObject_GetAttrString(obj, "name");
    } else if (index == 1) {
        memcpy(GET_TC(tc)->cStr, "data", sizeof(char) * 5);
        GET_TC(tc)->itemValue = get_values(obj);
        if (!GET_TC(tc)->itemValue) {
            return 0;
        }
    } else {
        PRINTMARK();
        return 0;
    }

    GET_TC(tc)->index++;
    PRINTMARK();
    return 1;
}

void Index_iterEnd(JSOBJ obj, JSONTypeContext *tc) { PRINTMARK(); }

JSOBJ Index_iterGetValue(JSOBJ obj, JSONTypeContext *tc) {
    return GET_TC(tc)->itemValue;
}

char *Index_iterGetName(JSOBJ obj, JSONTypeContext *tc, size_t *outLen) {
    *outLen = strlen(GET_TC(tc)->cStr);
    return GET_TC(tc)->cStr;
}

//=============================================================================
// pandas Series iteration functions
//=============================================================================
void Series_iterBegin(JSOBJ obj, JSONTypeContext *tc) {
    PyObjectEncoder *enc = (PyObjectEncoder *)tc->encoder;
    GET_TC(tc)->index = 0;
    GET_TC(tc)->cStr = PyObject_Malloc(20 * sizeof(char));
    enc->outputFormat = VALUES; // for contained series
    if (!GET_TC(tc)->cStr) {
        PyErr_NoMemory();
    }
    PRINTMARK();
}

int Series_iterNext(JSOBJ obj, JSONTypeContext *tc) {
    Py_ssize_t index;
    if (!GET_TC(tc)->cStr) {
        return 0;
    }

    index = GET_TC(tc)->index;
    Py_XDECREF(GET_TC(tc)->itemValue);
    if (index == 0) {
        memcpy(GET_TC(tc)->cStr, "name", sizeof(char) * 5);
        GET_TC(tc)->itemValue = PyObject_GetAttrString(obj, "name");
    } else if (index == 1) {
        memcpy(GET_TC(tc)->cStr, "index", sizeof(char) * 6);
        GET_TC(tc)->itemValue = PyObject_GetAttrString(obj, "index");
    } else if (index == 2) {
        memcpy(GET_TC(tc)->cStr, "data", sizeof(char) * 5);
        GET_TC(tc)->itemValue = get_values(obj);
        if (!GET_TC(tc)->itemValue) {
            return 0;
        }
    } else {
        PRINTMARK();
        return 0;
    }

    GET_TC(tc)->index++;
    PRINTMARK();
    return 1;
}

void Series_iterEnd(JSOBJ obj, JSONTypeContext *tc) {
    PyObjectEncoder *enc = (PyObjectEncoder *)tc->encoder;
    enc->outputFormat = enc->originalOutputFormat;
    PRINTMARK();
}

JSOBJ Series_iterGetValue(JSOBJ obj, JSONTypeContext *tc) {
    return GET_TC(tc)->itemValue;
}

char *Series_iterGetName(JSOBJ obj, JSONTypeContext *tc, size_t *outLen) {
    *outLen = strlen(GET_TC(tc)->cStr);
    return GET_TC(tc)->cStr;
}

//=============================================================================
// pandas DataFrame iteration functions
//=============================================================================
void DataFrame_iterBegin(JSOBJ obj, JSONTypeContext *tc) {
    PyObjectEncoder *enc = (PyObjectEncoder *)tc->encoder;
    GET_TC(tc)->index = 0;
    GET_TC(tc)->cStr = PyObject_Malloc(20 * sizeof(char));
    enc->outputFormat = VALUES; // for contained series & index
    if (!GET_TC(tc)->cStr) {
        PyErr_NoMemory();
    }
    PRINTMARK();
}

int DataFrame_iterNext(JSOBJ obj, JSONTypeContext *tc) {
    Py_ssize_t index;
    if (!GET_TC(tc)->cStr) {
        return 0;
    }

    index = GET_TC(tc)->index;
    Py_XDECREF(GET_TC(tc)->itemValue);
    if (index == 0) {
        memcpy(GET_TC(tc)->cStr, "columns", sizeof(char) * 8);
        GET_TC(tc)->itemValue = PyObject_GetAttrString(obj, "columns");
    } else if (index == 1) {
        memcpy(GET_TC(tc)->cStr, "index", sizeof(char) * 6);
        GET_TC(tc)->itemValue = PyObject_GetAttrString(obj, "index");
    } else if (index == 2) {
        memcpy(GET_TC(tc)->cStr, "data", sizeof(char) * 5);
        if (is_simple_frame(obj)) {
            GET_TC(tc)->itemValue = get_values(obj);
            if (!GET_TC(tc)->itemValue) {
                return 0;
            }
        } else {
            Py_INCREF(obj);
            GET_TC(tc)->itemValue = obj;
        }
    } else {
        PRINTMARK();
        return 0;
    }

    GET_TC(tc)->index++;
    PRINTMARK();
    return 1;
}

void DataFrame_iterEnd(JSOBJ obj, JSONTypeContext *tc) {
    PyObjectEncoder *enc = (PyObjectEncoder *)tc->encoder;
    enc->outputFormat = enc->originalOutputFormat;
    PRINTMARK();
}

JSOBJ DataFrame_iterGetValue(JSOBJ obj, JSONTypeContext *tc) {
    return GET_TC(tc)->itemValue;
}

char *DataFrame_iterGetName(JSOBJ obj, JSONTypeContext *tc, size_t *outLen) {
    *outLen = strlen(GET_TC(tc)->cStr);
    return GET_TC(tc)->cStr;
}

//=============================================================================
// Dict iteration functions
// itemName might converted to string (Python_Str). Do refCounting
// itemValue is borrowed from object (which is dict). No refCounting
//=============================================================================
void Dict_iterBegin(JSOBJ obj, JSONTypeContext *tc) {
    GET_TC(tc)->index = 0;
    PRINTMARK();
}

int Dict_iterNext(JSOBJ obj, JSONTypeContext *tc) {
    PyObject *itemNameTmp;

    if (GET_TC(tc)->itemName) {
        Py_DECREF(GET_TC(tc)->itemName);
        GET_TC(tc)->itemName = NULL;
    }

    if (!PyDict_Next((PyObject *)GET_TC(tc)->dictObj, &GET_TC(tc)->index,
                     &GET_TC(tc)->itemName, &GET_TC(tc)->itemValue)) {
        PRINTMARK();
        return 0;
    }

    if (PyUnicode_Check(GET_TC(tc)->itemName)) {
        GET_TC(tc)->itemName = PyUnicode_AsUTF8String(GET_TC(tc)->itemName);
    } else if (!PyBytes_Check(GET_TC(tc)->itemName)) {
        GET_TC(tc)->itemName = PyObject_Str(GET_TC(tc)->itemName);
        itemNameTmp = GET_TC(tc)->itemName;
        GET_TC(tc)->itemName = PyUnicode_AsUTF8String(GET_TC(tc)->itemName);
        Py_DECREF(itemNameTmp);
    } else {
        Py_INCREF(GET_TC(tc)->itemName);
    }
    PRINTMARK();
    return 1;
}

void Dict_iterEnd(JSOBJ obj, JSONTypeContext *tc) {
    if (GET_TC(tc)->itemName) {
        Py_DECREF(GET_TC(tc)->itemName);
        GET_TC(tc)->itemName = NULL;
    }
    Py_DECREF(GET_TC(tc)->dictObj);
    PRINTMARK();
}

JSOBJ Dict_iterGetValue(JSOBJ obj, JSONTypeContext *tc) {
    return GET_TC(tc)->itemValue;
}

char *Dict_iterGetName(JSOBJ obj, JSONTypeContext *tc, size_t *outLen) {
    *outLen = PyBytes_GET_SIZE(GET_TC(tc)->itemName);
    return PyBytes_AS_STRING(GET_TC(tc)->itemName);
}

void NpyArr_freeLabels(char **labels, npy_intp len) {
    npy_intp i;

    if (labels) {
        for (i = 0; i < len; i++) {
            PyObject_Free(labels[i]);
        }
        PyObject_Free(labels);
    }
}

/*
 * Function: NpyArr_encodeLabels
 * -----------------------------
 *
 * Builds an array of "encoded" labels.
 *
 * labels: PyArrayObject pointer for labels to be "encoded"
 * num : number of labels
 *
 * "encode" is quoted above because we aren't really doing encoding
 * For historical reasons this function would actually encode the entire
 * array into a separate buffer with a separate call to JSON_Encode
 * and would leave it to complex pointer manipulation from there to
 * unpack values as needed. To make things simpler and more idiomatic
 * this has instead just stringified any input save for datetime values,
 * which may need to be represented in various formats.
 */
char **NpyArr_encodeLabels(PyArrayObject *labels, PyObjectEncoder *enc,
                           npy_intp num) {
    // NOTE this function steals a reference to labels.
    PyObject *item = NULL;
    npy_intp i, stride, len;
    char **ret;
    char *dataptr, *cLabel;
    int type_num;
    PRINTMARK();

    if (!labels) {
        return 0;
    }

    if (PyArray_SIZE(labels) < num) {
        PyErr_SetString(
            PyExc_ValueError,
            "Label array sizes do not match corresponding data shape");
        Py_DECREF(labels);
        return 0;
    }

    ret = PyObject_Malloc(sizeof(char *) * num);
    if (!ret) {
        PyErr_NoMemory();
        Py_DECREF(labels);
        return 0;
    }

    for (i = 0; i < num; i++) {
        ret[i] = NULL;
    }

    stride = PyArray_STRIDE(labels, 0);
    dataptr = PyArray_DATA(labels);
    type_num = PyArray_TYPE(labels);

    for (i = 0; i < num; i++) {
        item = PyArray_GETITEM(labels, dataptr);
        if (!item) {
            NpyArr_freeLabels(ret, num);
            ret = 0;
            break;
        }

        // TODO: for any matches on type_num (date and timedeltas) should use a
        // vectorized solution to convert to epoch or iso formats
        if (enc->datetimeIso &&
            (type_num == NPY_TIMEDELTA || PyDelta_Check(item))) {
            PyObject *td = PyObject_CallFunction(cls_timedelta, "(O)", item);
            if (td == NULL) {
                Py_DECREF(item);
                NpyArr_freeLabels(ret, num);
                ret = 0;
                break;
            }

            PyObject *iso = PyObject_CallMethod(td, "isoformat", NULL);
            Py_DECREF(td);
            if (iso == NULL) {
                Py_DECREF(item);
                NpyArr_freeLabels(ret, num);
                ret = 0;
                break;
            }

            cLabel = (char *)PyUnicode_AsUTF8(iso);
            Py_DECREF(iso);
            len = strlen(cLabel);
        } else if (PyTypeNum_ISDATETIME(type_num) || PyDateTime_Check(item) ||
                   PyDate_Check(item)) {
            PyObject *ts = PyObject_CallFunction(cls_timestamp, "(O)", item);
            if (ts == NULL) {
                Py_DECREF(item);
                NpyArr_freeLabels(ret, num);
                ret = 0;
                break;
            }

            if (enc->datetimeIso) {
                PyObject *iso = PyObject_CallMethod(ts, "isoformat", NULL);
                Py_DECREF(ts);
                if (iso == NULL) {
                    Py_DECREF(item);
                    NpyArr_freeLabels(ret, num);
                    ret = 0;
                    break;
                }

                cLabel = (char *)PyUnicode_AsUTF8(iso);
                Py_DECREF(iso);
                len = strlen(cLabel);
            } else {
                npy_int64 value;
                // TODO: refactor to not duplicate what goes on in
                // beginTypeContext
                if (PyObject_HasAttrString(ts, "value")) {
                    PRINTMARK();
                    value = get_long_attr(ts, "value");
                } else {
                    PRINTMARK();
                    value = total_seconds(ts) *
                            1000000000LL; // nanoseconds per second
                }
                Py_DECREF(ts);

                switch (enc->datetimeUnit) {
                case NPY_FR_ns:
                    break;
                case NPY_FR_us:
                    value /= 1000LL;
                    break;
                case NPY_FR_ms:
                    value /= 1000000LL;
                    break;
                case NPY_FR_s:
                    value /= 1000000000LL;
                    break;
                default:
                    Py_DECREF(item);
                    NpyArr_freeLabels(ret, num);
                    ret = 0;
                    break;
                }

                char buf[21] = {0}; // 21 chars for 2**63 as string
                cLabel = buf;
                sprintf(buf, "%" NPY_INT64_FMT, value);
                len = strlen(cLabel);
            }
        } else { // Fallack to string representation
            PyObject *str = PyObject_Str(item);
            if (str == NULL) {
                Py_DECREF(item);
                NpyArr_freeLabels(ret, num);
                ret = 0;
                break;
            }

            cLabel = (char *)PyUnicode_AsUTF8(str);
            Py_DECREF(str);
            len = strlen(cLabel);
        }

        Py_DECREF(item);
        // Add 1 to include NULL terminator
        ret[i] = PyObject_Malloc(len + 1);
        memcpy(ret[i], cLabel, len + 1);

        if (PyErr_Occurred()) {
            NpyArr_freeLabels(ret, num);
            ret = 0;
            break;
        }

        if (!ret[i]) {
            PyErr_NoMemory();
            ret = 0;
            break;
        }

        dataptr += stride;
    }

    Py_DECREF(labels);
    return ret;
}

void Object_invokeDefaultHandler(PyObject *obj, PyObjectEncoder *enc) {
    PyObject *tmpObj = NULL;
    PRINTMARK();
    tmpObj = PyObject_CallFunctionObjArgs(enc->defaultHandler, obj, NULL);
    if (!PyErr_Occurred()) {
        if (tmpObj == NULL) {
            PyErr_SetString(PyExc_TypeError,
                            "Failed to execute default handler");
        } else {
            encode(tmpObj, (JSONObjectEncoder *)enc, NULL, 0);
        }
    }
    Py_XDECREF(tmpObj);
    return;
}

void Object_beginTypeContext(JSOBJ _obj, JSONTypeContext *tc) {
    PyObject *obj, *exc, *toDictFunc, *tmpObj, *values;
    TypeContext *pc;
    PyObjectEncoder *enc;
    double val;
    npy_int64 value;
    int base;
    PRINTMARK();

    tc->prv = NULL;

    if (!_obj) {
        tc->type = JT_INVALID;
        return;
    }

    obj = (PyObject *)_obj;
    enc = (PyObjectEncoder *)tc->encoder;

    if (enc->npyType >= 0) {
        PRINTMARK();
        tc->prv = &(enc->basicTypeContext);
        tc->type = NpyTypeToJSONType(obj, tc, enc->npyType, enc->npyValue);

        if (tc->type == JT_INVALID) {
            if (enc->defaultHandler) {
                enc->npyType = -1;
                PRINTMARK();
                Object_invokeDefaultHandler(
                    enc->npyCtxtPassthru->getitem(enc->npyValue,
                                                  enc->npyCtxtPassthru->array),
                    enc);
            } else {
                PyErr_Format(PyExc_RuntimeError, "Unhandled numpy dtype %d",
                             enc->npyType);
            }
        }
        enc->npyCtxtPassthru = NULL;
        enc->npyType = -1;
        return;
    }

    if (PyBool_Check(obj)) {
        PRINTMARK();
        tc->type = (obj == Py_True) ? JT_TRUE : JT_FALSE;
        return;
    } else if (obj == Py_None) {
        PRINTMARK();
        tc->type = JT_NULL;
        return;
    }

    pc = createTypeContext();
    if (!pc) {
        tc->type = JT_INVALID;
        return;
    }
    tc->prv = pc;

    if (PyIter_Check(obj) ||
        (PyArray_Check(obj) && !PyArray_CheckScalar(obj))) {
        PRINTMARK();
        goto ISITERABLE;
    }

    if (PyLong_Check(obj)) {
        PRINTMARK();
        tc->type = JT_LONG;
        GET_TC(tc)->longValue = PyLong_AsLongLong(obj);

        exc = PyErr_Occurred();

        if (exc && PyErr_ExceptionMatches(PyExc_OverflowError)) {
            PRINTMARK();
            goto INVALID;
        }

        return;
    } else if (PyFloat_Check(obj)) {
        PRINTMARK();
        val = PyFloat_AS_DOUBLE(obj);
        if (npy_isnan(val) || npy_isinf(val)) {
            tc->type = JT_NULL;
        } else {
            GET_TC(tc)->doubleValue = val;
            tc->type = JT_DOUBLE;
        }
        return;
    } else if (PyBytes_Check(obj)) {
        PRINTMARK();
        pc->PyTypeToJSON = PyBytesToUTF8;
        tc->type = JT_UTF8;
        return;
    } else if (PyUnicode_Check(obj)) {
        PRINTMARK();
        pc->PyTypeToJSON = PyUnicodeToUTF8;
        tc->type = JT_UTF8;
        return;
    } else if (PyObject_TypeCheck(obj, type_decimal)) {
        PRINTMARK();
        GET_TC(tc)->doubleValue = PyFloat_AsDouble(obj);
        tc->type = JT_DOUBLE;
        return;
    } else if (PyDateTime_Check(obj) || PyDate_Check(obj)) {
        if (PyObject_TypeCheck(obj, cls_nat)) {
            PRINTMARK();
            tc->type = JT_NULL;
            return;
        }

        PRINTMARK();
        if (enc->datetimeIso) {
            PRINTMARK();
            pc->PyTypeToJSON = PyDateTimeToJSON;
            tc->type = JT_UTF8;
        } else {
            PRINTMARK();
            // TODO: last argument here is unused; should decouple string
            // from long datetimelike conversion routines
            PyDateTimeToJSON(obj, tc, &(GET_TC(tc)->longValue), 0);
            tc->type = JT_LONG;
        }
        return;
    } else if (PyTime_Check(obj)) {
        PRINTMARK();
        pc->PyTypeToJSON = PyTimeToJSON;
        tc->type = JT_UTF8;
        return;
    } else if (PyArray_IsScalar(obj, Datetime)) {
        PRINTMARK();
        if (((PyDatetimeScalarObject *)obj)->obval == get_nat()) {
            PRINTMARK();
            tc->type = JT_NULL;
            return;
        }

        PRINTMARK();
        pc->PyTypeToJSON = NpyDateTimeScalarToJSON;
        tc->type = enc->datetimeIso ? JT_UTF8 : JT_LONG;
        return;
    } else if (PyDelta_Check(obj)) {
        if (PyObject_HasAttrString(obj, "value")) {
            PRINTMARK();
            value = get_long_attr(obj, "value");
        } else {
            PRINTMARK();
            value = total_seconds(obj) * 1000000000LL; // nanoseconds per second
        }

        base = ((PyObjectEncoder *)tc->encoder)->datetimeUnit;
        switch (base) {
        case NPY_FR_ns:
            break;
        case NPY_FR_us:
            value /= 1000LL;
            break;
        case NPY_FR_ms:
            value /= 1000000LL;
            break;
        case NPY_FR_s:
            value /= 1000000000LL;
            break;
        }

        exc = PyErr_Occurred();

        if (exc && PyErr_ExceptionMatches(PyExc_OverflowError)) {
            PRINTMARK();
            goto INVALID;
        }

        if (value == get_nat()) {
            PRINTMARK();
            tc->type = JT_NULL;
            return;
        }

        GET_TC(tc)->longValue = value;

        PRINTMARK();
        tc->type = JT_LONG;
        return;
    } else if (PyArray_IsScalar(obj, Integer)) {
        PRINTMARK();
        tc->type = JT_LONG;
        PyArray_CastScalarToCtype(obj, &(GET_TC(tc)->longValue),
                                  PyArray_DescrFromType(NPY_INT64));

        exc = PyErr_Occurred();

        if (exc && PyErr_ExceptionMatches(PyExc_OverflowError)) {
            PRINTMARK();
            goto INVALID;
        }

        return;
    } else if (PyArray_IsScalar(obj, Bool)) {
        PRINTMARK();
        PyArray_CastScalarToCtype(obj, &(GET_TC(tc)->longValue),
                                  PyArray_DescrFromType(NPY_BOOL));
        tc->type = (GET_TC(tc)->longValue) ? JT_TRUE : JT_FALSE;
        return;
    } else if (PyArray_IsScalar(obj, Float) || PyArray_IsScalar(obj, Double)) {
        PRINTMARK();
        PyArray_CastScalarToCtype(obj, &(GET_TC(tc)->doubleValue),
                                  PyArray_DescrFromType(NPY_DOUBLE));
        tc->type = JT_DOUBLE;
        return;
    } else if (PyArray_Check(obj) && PyArray_CheckScalar(obj)) {
        PyErr_Format(PyExc_TypeError,
                     "%R (0d array) is not JSON serializable at the moment",
                     obj);
        goto INVALID;
    }

ISITERABLE:

    if (PyObject_TypeCheck(obj, cls_index)) {
        if (enc->outputFormat == SPLIT) {
            PRINTMARK();
            tc->type = JT_OBJECT;
            pc->iterBegin = Index_iterBegin;
            pc->iterEnd = Index_iterEnd;
            pc->iterNext = Index_iterNext;
            pc->iterGetValue = Index_iterGetValue;
            pc->iterGetName = Index_iterGetName;
            return;
        }

        pc->newObj = get_values(obj);
        if (pc->newObj) {
            PRINTMARK();
            tc->type = JT_ARRAY;
            pc->iterBegin = NpyArr_iterBegin;
            pc->iterEnd = NpyArr_iterEnd;
            pc->iterNext = NpyArr_iterNext;
            pc->iterGetValue = NpyArr_iterGetValue;
            pc->iterGetName = NpyArr_iterGetName;
        } else {
            goto INVALID;
        }

        return;
    } else if (PyObject_TypeCheck(obj, cls_series)) {
        if (enc->outputFormat == SPLIT) {
            PRINTMARK();
            tc->type = JT_OBJECT;
            pc->iterBegin = Series_iterBegin;
            pc->iterEnd = Series_iterEnd;
            pc->iterNext = Series_iterNext;
            pc->iterGetValue = Series_iterGetValue;
            pc->iterGetName = Series_iterGetName;
            return;
        }

        pc->newObj = get_values(obj);
        if (!pc->newObj) {
            goto INVALID;
        }

        if (enc->outputFormat == INDEX || enc->outputFormat == COLUMNS) {
            PRINTMARK();
            tc->type = JT_OBJECT;
            tmpObj = PyObject_GetAttrString(obj, "index");
            if (!tmpObj) {
                goto INVALID;
            }
            values = get_values(tmpObj);
            Py_DECREF(tmpObj);
            if (!values) {
                goto INVALID;
            }
            pc->columnLabelsLen = PyArray_DIM(pc->newObj, 0);
            pc->columnLabels = NpyArr_encodeLabels((PyArrayObject *)values, enc,
                                                   pc->columnLabelsLen);
            if (!pc->columnLabels) {
                goto INVALID;
            }
        } else {
            PRINTMARK();
            tc->type = JT_ARRAY;
        }
        pc->iterBegin = NpyArr_iterBegin;
        pc->iterEnd = NpyArr_iterEnd;
        pc->iterNext = NpyArr_iterNext;
        pc->iterGetValue = NpyArr_iterGetValue;
        pc->iterGetName = NpyArr_iterGetName;
        return;
    } else if (PyArray_Check(obj)) {
        if (enc->npyCtxtPassthru) {
            PRINTMARK();
            pc->npyarr = enc->npyCtxtPassthru;
            tc->type = (pc->npyarr->columnLabels ? JT_OBJECT : JT_ARRAY);

            pc->iterBegin = NpyArrPassThru_iterBegin;
            pc->iterNext = NpyArr_iterNext;
            pc->iterEnd = NpyArrPassThru_iterEnd;
            pc->iterGetValue = NpyArr_iterGetValue;
            pc->iterGetName = NpyArr_iterGetName;

            enc->npyCtxtPassthru = NULL;
            return;
        }

        PRINTMARK();
        tc->type = JT_ARRAY;
        pc->iterBegin = NpyArr_iterBegin;
        pc->iterEnd = NpyArr_iterEnd;
        pc->iterNext = NpyArr_iterNext;
        pc->iterGetValue = NpyArr_iterGetValue;
        pc->iterGetName = NpyArr_iterGetName;
        return;
    } else if (PyObject_TypeCheck(obj, cls_dataframe)) {
        if (enc->blkCtxtPassthru) {
            PRINTMARK();
            pc->pdblock = enc->blkCtxtPassthru;
            tc->type =
                (pc->pdblock->npyCtxts[0]->columnLabels ? JT_OBJECT : JT_ARRAY);

            pc->iterBegin = PdBlockPassThru_iterBegin;
            pc->iterEnd = PdBlockPassThru_iterEnd;
            pc->iterNext = PdBlock_iterNextItem;
            pc->iterGetName = PdBlock_iterGetName;
            pc->iterGetValue = NpyArr_iterGetValue;

            enc->blkCtxtPassthru = NULL;
            return;
        }

        if (enc->outputFormat == SPLIT) {
            PRINTMARK();
            tc->type = JT_OBJECT;
            pc->iterBegin = DataFrame_iterBegin;
            pc->iterEnd = DataFrame_iterEnd;
            pc->iterNext = DataFrame_iterNext;
            pc->iterGetValue = DataFrame_iterGetValue;
            pc->iterGetName = DataFrame_iterGetName;
            return;
        }

        PRINTMARK();
        if (is_simple_frame(obj)) {
            pc->iterBegin = NpyArr_iterBegin;
            pc->iterEnd = NpyArr_iterEnd;
            pc->iterNext = NpyArr_iterNext;
            pc->iterGetName = NpyArr_iterGetName;

            pc->newObj = get_values(obj);
            if (!pc->newObj) {
                goto INVALID;
            }
        } else {
            pc->iterBegin = PdBlock_iterBegin;
            pc->iterEnd = PdBlock_iterEnd;
            pc->iterNext = PdBlock_iterNext;
            pc->iterGetName = PdBlock_iterGetName;
        }
        pc->iterGetValue = NpyArr_iterGetValue;

        if (enc->outputFormat == VALUES) {
            PRINTMARK();
            tc->type = JT_ARRAY;
        } else if (enc->outputFormat == RECORDS) {
            PRINTMARK();
            tc->type = JT_ARRAY;
            tmpObj = PyObject_GetAttrString(obj, "columns");
            if (!tmpObj) {
                goto INVALID;
            }
            values = get_values(tmpObj);
            if (!values) {
                Py_DECREF(tmpObj);
                goto INVALID;
            }
            pc->columnLabelsLen = PyObject_Size(tmpObj);
            pc->columnLabels = NpyArr_encodeLabels((PyArrayObject *)values, enc,
                                                   pc->columnLabelsLen);
            Py_DECREF(tmpObj);
            if (!pc->columnLabels) {
                goto INVALID;
            }
        } else if (enc->outputFormat == INDEX || enc->outputFormat == COLUMNS) {
            PRINTMARK();
            tc->type = JT_OBJECT;
            tmpObj = (enc->outputFormat == INDEX
                          ? PyObject_GetAttrString(obj, "index")
                          : PyObject_GetAttrString(obj, "columns"));
            if (!tmpObj) {
                goto INVALID;
            }
            values = get_values(tmpObj);
            if (!values) {
                Py_DECREF(tmpObj);
                goto INVALID;
            }
            pc->rowLabelsLen = PyObject_Size(tmpObj);
            pc->rowLabels = NpyArr_encodeLabels((PyArrayObject *)values, enc,
                                                pc->rowLabelsLen);
            Py_DECREF(tmpObj);
            tmpObj = (enc->outputFormat == INDEX
                          ? PyObject_GetAttrString(obj, "columns")
                          : PyObject_GetAttrString(obj, "index"));
            if (!tmpObj) {
                NpyArr_freeLabels(pc->rowLabels, pc->rowLabelsLen);
                pc->rowLabels = NULL;
                goto INVALID;
            }
            values = get_values(tmpObj);
            if (!values) {
                Py_DECREF(tmpObj);
                NpyArr_freeLabels(pc->rowLabels, pc->rowLabelsLen);
                pc->rowLabels = NULL;
                goto INVALID;
            }
            pc->columnLabelsLen = PyObject_Size(tmpObj);
            pc->columnLabels = NpyArr_encodeLabels((PyArrayObject *)values, enc,
                                                   pc->columnLabelsLen);
            Py_DECREF(tmpObj);
            if (!pc->columnLabels) {
                NpyArr_freeLabels(pc->rowLabels, pc->rowLabelsLen);
                pc->rowLabels = NULL;
                goto INVALID;
            }

            if (enc->outputFormat == COLUMNS) {
                PRINTMARK();
                pc->transpose = 1;
            }
        } else {
            goto INVALID;
        }
        return;
    } else if (PyDict_Check(obj)) {
        PRINTMARK();
        tc->type = JT_OBJECT;
        pc->iterBegin = Dict_iterBegin;
        pc->iterEnd = Dict_iterEnd;
        pc->iterNext = Dict_iterNext;
        pc->iterGetValue = Dict_iterGetValue;
        pc->iterGetName = Dict_iterGetName;
        pc->dictObj = obj;
        Py_INCREF(obj);

        return;
    } else if (PyList_Check(obj)) {
        PRINTMARK();
        tc->type = JT_ARRAY;
        pc->iterBegin = List_iterBegin;
        pc->iterEnd = List_iterEnd;
        pc->iterNext = List_iterNext;
        pc->iterGetValue = List_iterGetValue;
        pc->iterGetName = List_iterGetName;
        return;
    } else if (PyTuple_Check(obj)) {
        PRINTMARK();
        tc->type = JT_ARRAY;
        pc->iterBegin = Tuple_iterBegin;
        pc->iterEnd = Tuple_iterEnd;
        pc->iterNext = Tuple_iterNext;
        pc->iterGetValue = Tuple_iterGetValue;
        pc->iterGetName = Tuple_iterGetName;
        return;
    } else if (PyAnySet_Check(obj)) {
        PRINTMARK();
        tc->type = JT_ARRAY;
        pc->iterBegin = Iter_iterBegin;
        pc->iterEnd = Iter_iterEnd;
        pc->iterNext = Iter_iterNext;
        pc->iterGetValue = Iter_iterGetValue;
        pc->iterGetName = Iter_iterGetName;
        return;
    }

    toDictFunc = PyObject_GetAttrString(obj, "toDict");

    if (toDictFunc) {
        PyObject *tuple = PyTuple_New(0);
        PyObject *toDictResult = PyObject_Call(toDictFunc, tuple, NULL);
        Py_DECREF(tuple);
        Py_DECREF(toDictFunc);

        if (toDictResult == NULL) {
            PyErr_Clear();
            tc->type = JT_NULL;
            return;
        }

        if (!PyDict_Check(toDictResult)) {
            Py_DECREF(toDictResult);
            tc->type = JT_NULL;
            return;
        }

        PRINTMARK();
        tc->type = JT_OBJECT;
        pc->iterBegin = Dict_iterBegin;
        pc->iterEnd = Dict_iterEnd;
        pc->iterNext = Dict_iterNext;
        pc->iterGetValue = Dict_iterGetValue;
        pc->iterGetName = Dict_iterGetName;
        pc->dictObj = toDictResult;
        return;
    }

    PyErr_Clear();

    if (enc->defaultHandler) {
        Object_invokeDefaultHandler(obj, enc);
        goto INVALID;
    }

    PRINTMARK();
    tc->type = JT_OBJECT;
    pc->iterBegin = Dir_iterBegin;
    pc->iterEnd = Dir_iterEnd;
    pc->iterNext = Dir_iterNext;
    pc->iterGetValue = Dir_iterGetValue;
    pc->iterGetName = Dir_iterGetName;
    return;

INVALID:
    tc->type = JT_INVALID;
    PyObject_Free(tc->prv);
    tc->prv = NULL;
    return;
}

void Object_endTypeContext(JSOBJ obj, JSONTypeContext *tc) {
    PRINTMARK();
    if (tc->prv) {
        Py_XDECREF(GET_TC(tc)->newObj);
        GET_TC(tc)->newObj = NULL;
        NpyArr_freeLabels(GET_TC(tc)->rowLabels, GET_TC(tc)->rowLabelsLen);
        GET_TC(tc)->rowLabels = NULL;
        NpyArr_freeLabels(GET_TC(tc)->columnLabels,
                          GET_TC(tc)->columnLabelsLen);
        GET_TC(tc)->columnLabels = NULL;

        PyObject_Free(GET_TC(tc)->cStr);
        GET_TC(tc)->cStr = NULL;
        if (tc->prv !=
            &(((PyObjectEncoder *)tc->encoder)->basicTypeContext)) { // NOLINT
            PyObject_Free(tc->prv);
        }
        tc->prv = NULL;
    }
}

const char *Object_getStringValue(JSOBJ obj, JSONTypeContext *tc,
                                  size_t *_outLen) {
    return GET_TC(tc)->PyTypeToJSON(obj, tc, NULL, _outLen);
}

JSINT64 Object_getLongValue(JSOBJ obj, JSONTypeContext *tc) {
    return GET_TC(tc)->longValue;
}

double Object_getDoubleValue(JSOBJ obj, JSONTypeContext *tc) {
    return GET_TC(tc)->doubleValue;
}

static void Object_releaseObject(JSOBJ _obj) { Py_DECREF((PyObject *)_obj); }

void Object_iterBegin(JSOBJ obj, JSONTypeContext *tc) {
    GET_TC(tc)->iterBegin(obj, tc);
}

int Object_iterNext(JSOBJ obj, JSONTypeContext *tc) {
    return GET_TC(tc)->iterNext(obj, tc);
}

void Object_iterEnd(JSOBJ obj, JSONTypeContext *tc) {
    GET_TC(tc)->iterEnd(obj, tc);
}

JSOBJ Object_iterGetValue(JSOBJ obj, JSONTypeContext *tc) {
    return GET_TC(tc)->iterGetValue(obj, tc);
}

char *Object_iterGetName(JSOBJ obj, JSONTypeContext *tc, size_t *outLen) {
    return GET_TC(tc)->iterGetName(obj, tc, outLen);
}

PyObject *objToJSON(PyObject *self, PyObject *args, PyObject *kwargs) {
    static char *kwlist[] = {"obj",
                             "ensure_ascii",
                             "double_precision",
                             "encode_html_chars",
                             "orient",
                             "date_unit",
                             "iso_dates",
                             "default_handler",
                             "indent",
                             NULL};

    char buffer[65536];
    char *ret;
    PyObject *newobj;
    PyObject *oinput = NULL;
    PyObject *oensureAscii = NULL;
    int idoublePrecision = 10; // default double precision setting
    PyObject *oencodeHTMLChars = NULL;
    char *sOrient = NULL;
    char *sdateFormat = NULL;
    PyObject *oisoDates = 0;
    PyObject *odefHandler = 0;
    int indent = 0;

    PyObjectEncoder pyEncoder = {{
        Object_beginTypeContext,
        Object_endTypeContext,
        Object_getStringValue,
        Object_getLongValue,
        NULL, // getIntValue is unused
        Object_getDoubleValue,
        Object_iterBegin,
        Object_iterNext,
        Object_iterEnd,
        Object_iterGetValue,
        Object_iterGetName,
        Object_releaseObject,
        PyObject_Malloc,
        PyObject_Realloc,
        PyObject_Free,
        -1, // recursionMax
        idoublePrecision,
        1, // forceAscii
        0, // encodeHTMLChars
        0, // indent
    }};
    JSONObjectEncoder *encoder = (JSONObjectEncoder *)&pyEncoder;

    pyEncoder.npyCtxtPassthru = NULL;
    pyEncoder.blkCtxtPassthru = NULL;
    pyEncoder.npyType = -1;
    pyEncoder.npyValue = NULL;
    pyEncoder.datetimeIso = 0;
    pyEncoder.datetimeUnit = NPY_FR_ms;
    pyEncoder.outputFormat = COLUMNS;
    pyEncoder.defaultHandler = 0;
    pyEncoder.basicTypeContext.newObj = NULL;
    pyEncoder.basicTypeContext.dictObj = NULL;
    pyEncoder.basicTypeContext.itemValue = NULL;
    pyEncoder.basicTypeContext.itemName = NULL;
    pyEncoder.basicTypeContext.attrList = NULL;
    pyEncoder.basicTypeContext.iterator = NULL;
    pyEncoder.basicTypeContext.cStr = NULL;
    pyEncoder.basicTypeContext.npyarr = NULL;
    pyEncoder.basicTypeContext.rowLabels = NULL;
    pyEncoder.basicTypeContext.columnLabels = NULL;

    PRINTMARK();

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|OiOssOOi", kwlist,
                                     &oinput, &oensureAscii, &idoublePrecision,
                                     &oencodeHTMLChars, &sOrient, &sdateFormat,
                                     &oisoDates, &odefHandler, &indent)) {
        return NULL;
    }

    if (oensureAscii != NULL && !PyObject_IsTrue(oensureAscii)) {
        encoder->forceASCII = 0;
    }

    if (oencodeHTMLChars != NULL && PyObject_IsTrue(oencodeHTMLChars)) {
        encoder->encodeHTMLChars = 1;
    }

    if (idoublePrecision > JSON_DOUBLE_MAX_DECIMALS || idoublePrecision < 0) {
        PyErr_Format(
            PyExc_ValueError,
            "Invalid value '%d' for option 'double_precision', max is '%u'",
            idoublePrecision, JSON_DOUBLE_MAX_DECIMALS);
        return NULL;
    }
    encoder->doublePrecision = idoublePrecision;

    if (sOrient != NULL) {
        if (strcmp(sOrient, "records") == 0) {
            pyEncoder.outputFormat = RECORDS;
        } else if (strcmp(sOrient, "index") == 0) {
            pyEncoder.outputFormat = INDEX;
        } else if (strcmp(sOrient, "split") == 0) {
            pyEncoder.outputFormat = SPLIT;
        } else if (strcmp(sOrient, "values") == 0) {
            pyEncoder.outputFormat = VALUES;
        } else if (strcmp(sOrient, "columns") != 0) {
            PyErr_Format(PyExc_ValueError,
                         "Invalid value '%s' for option 'orient'", sOrient);
            return NULL;
        }
    }

    if (sdateFormat != NULL) {
        if (strcmp(sdateFormat, "s") == 0) {
            pyEncoder.datetimeUnit = NPY_FR_s;
        } else if (strcmp(sdateFormat, "ms") == 0) {
            pyEncoder.datetimeUnit = NPY_FR_ms;
        } else if (strcmp(sdateFormat, "us") == 0) {
            pyEncoder.datetimeUnit = NPY_FR_us;
        } else if (strcmp(sdateFormat, "ns") == 0) {
            pyEncoder.datetimeUnit = NPY_FR_ns;
        } else {
            PyErr_Format(PyExc_ValueError,
                         "Invalid value '%s' for option 'date_unit'",
                         sdateFormat);
            return NULL;
        }
    }

    if (oisoDates != NULL && PyObject_IsTrue(oisoDates)) {
        pyEncoder.datetimeIso = 1;
    }

    if (odefHandler != NULL && odefHandler != Py_None) {
        if (!PyCallable_Check(odefHandler)) {
            PyErr_SetString(PyExc_TypeError, "Default handler is not callable");
            return NULL;
        }
        pyEncoder.defaultHandler = odefHandler;
    }

    encoder->indent = indent;

    pyEncoder.originalOutputFormat = pyEncoder.outputFormat;
    PRINTMARK();
    ret = JSON_EncodeObject(oinput, encoder, buffer, sizeof(buffer));
    PRINTMARK();
    if (PyErr_Occurred()) {
        PRINTMARK();
        return NULL;
    }

    if (encoder->errorMsg) {
        PRINTMARK();
        if (ret != buffer) {
            encoder->free(ret);
        }

        PyErr_Format(PyExc_OverflowError, "%s", encoder->errorMsg);
        return NULL;
    }

    newobj = PyUnicode_FromString(ret);

    if (ret != buffer) {
        encoder->free(ret);
    }

    PRINTMARK();

    return newobj;
}
