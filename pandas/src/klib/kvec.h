/* The MIT License

   Copyright (c) 2008, by Attractive Chaos <attractor@live.co.uk>

   Permission is hereby granted, free of charge, to any person obtaining
   a copy of this software and associated documentation files (the
   "Software"), to deal in the Software without restriction, including
   without limitation the rights to use, copy, modify, merge, publish,
   distribute, sublicense, and/or sell copies of the Software, and to
   permit persons to whom the Software is furnished to do so, subject to
   the following conditions:

   The above copyright notice and this permission notice shall be
   included in all copies or substantial portions of the Software.

   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
   EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
   MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
   NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
   BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
   ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
   CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
   SOFTWARE.
*/

/*
  An example:

#include "kvec.h"
int main() {
	kvec_t(int) array;
	kv_init(array);
	kv_push(int, array, 10); // append
	kv_a(int, array, 20) = 5; // dynamic
	kv_A(array, 20) = 4; // static
	kv_destroy(array);
	return 0;
}
*/

/*
  2008-09-22 (0.1.0):

	* The initial version.

*/

#ifndef AC_KVEC_H
#define AC_KVEC_H

#include <stdlib.h>
#include <Python.h>
#include <numpy/ndarraytypes.h>

#ifndef PANDAS_INLINE
  #if defined(__GNUC__)
    #define PANDAS_INLINE static __inline__
  #elif defined(_MSC_VER)
    #define PANDAS_INLINE static __inline
  #elif defined (__STDC_VERSION__) && __STDC_VERSION__ >= 199901L
    #define PANDAS_INLINE static inline
  #else
    #define PANDAS_INLINE
  #endif
#endif

#define kv_roundup32(x) (--(x), (x)|=(x)>>1, (x)|=(x)>>2, (x)|=(x)>>4, (x)|=(x)>>8, (x)|=(x)>>16, ++(x))

#define kvec_t(type) struct { size_t n, m; type *a; }
#define kv_init(v) ((v).n = (v).m = 0, (v).a = 0)
#define kv_destroy(v) free((v).a)
#define kv_A(v, i) ((v).a[(i)])
#define kv_pop(v) ((v).a[--(v).n])
#define kv_size(v) ((v).n)
#define kv_max(v) ((v).m)

#define kv_resize(type, v, s)  ((v).m = (s), (v).a = (type*)realloc((v).a, sizeof(type) * (v).m))

#define kv_copy(type, v1, v0) do {							\
		if ((v1).m < (v0).n) kv_resize(type, v1, (v0).n);	\
		(v1).n = (v0).n;									\
		memcpy((v1).a, (v0).a, sizeof(type) * (v0).n);		\
	} while (0)												\

#define kv_push(type, v, x) do {									\
		if ((v)->n == (v)->m) {										\
			(v)->m = (v)->m? (v)->m<<1 : 2;							\
			(v)->a = (type*)realloc((v)->a, sizeof(type) * (v)->m);	\
		}															\
		(v)->a[(v)->n++] = (x);										\
	} while (0)

#define kv_pushp(type, v) (((v).n == (v).m)?							\
						   ((v).m = ((v).m? (v).m<<1 : 2),				\
							(v).a = (type*)realloc((v).a, sizeof(type) * (v).m), 0)	\
						   : 0), ((v).a + ((v).n++))

#define kv_a(type, v, i) ((v).m <= (size_t)(i)?						\
						  ((v).m = (v).n = (i) + 1, kv_roundup32((v).m), \
						   (v).a = (type*)realloc((v).a, sizeof(type) * (v).m), 0) \
						  : (v).n <= (size_t)(i)? (v).n = (i)			\
						  : 0), (v).a[(i)]

// #define kv_int64_push(v, x) (kv_push(int64_t, (v), (x)))

typedef struct {
  size_t n, m;
  int64_t* a;
} kv_int64_t;

typedef struct {
  size_t n, m;
  double* a;
} kv_double;

typedef struct {
  size_t n, m;
  PyObject** a;
} kv_object_t;

void PANDAS_INLINE kv_object_push(kv_object_t *v, PyObject *x) {
  do {
		if (v->n == v->m) {
			v->m = v->m? v->m<<1 : 2;
			v->a = (PyObject**)realloc(v->a, sizeof(PyObject*) * v->m);
		}
		v->a[v->n++] = x;
	} while (0);
  // kv_push(PyObject*, v, x);
  Py_INCREF(x);
}

void PANDAS_INLINE kv_int64_push(kv_int64_t *v, int64_t x) {
  kv_push(int64_t, v, x);
}

void PANDAS_INLINE kv_double_push(kv_double *v, double x) {
  kv_push(double, v, x);
}

void PANDAS_INLINE kv_object_destroy(kv_object_t *v) {
  int i;
  for (i = 0; i < v->n; ++i)
  {
    Py_XDECREF(v->a[i]);
  }
  free(v->a);
}


#endif
