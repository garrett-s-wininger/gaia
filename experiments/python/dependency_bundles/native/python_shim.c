/* GIL-held CPython bridge: the returned bytes own their storage. */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <marshal.h>
#include <stdint.h>
#include <string.h>

extern int32_t gaia_open(const char *, const char *, const char *, int32_t, void **);
extern void gaia_catalog(void *, const unsigned char **, const unsigned char **, uint64_t *, uint64_t *, uint64_t *);
extern int32_t gaia_read(void *, uint64_t, const unsigned char **, uint64_t *);
extern void gaia_close(void *);
extern int32_t gaia_live_open(const char *,const char *,const char *,int32_t,uint64_t,void **);
extern void gaia_live_close(void *);
extern int64_t gaia_live_lookup(void *,const char *,int32_t);
extern int32_t gaia_live_name(void *,uint64_t,const unsigned char **,const unsigned char **,uint64_t *,uint64_t *,int32_t *);
extern void gaia_live_stats(void *,uint64_t (*)[6]);
extern int32_t gaia_live_children(void *,uint64_t,int32_t,int64_t *,int64_t *);
extern int64_t gaia_live_next(void *,uint64_t,int32_t);
extern int32_t gaia_live_dir_name(void *,uint64_t,const unsigned char **,uint64_t *);
extern int64_t gaia_live_subdir(void *,uint64_t,uint64_t);
extern int32_t gaia_mapped_open(const char *,const char *,const char *,const char *,const char *,int32_t,uint64_t,void **);
extern void gaia_live_export(void *,const unsigned char **,uint64_t *);
extern void gaia_live_phases(void *,double (*)[3]);
extern int32_t gaia_unified_open(const char *,const char *,const char *,const char *,int32_t,uint64_t,void **);
typedef struct { void *reader; int active_decodes, close_pending, live; } Handle;
static const char *capsule_name = "gaia.native_reader.v1";
static void release_reader(Handle *h) {
    if (h->reader) { if (h->live) gaia_live_close(h->reader); else gaia_close(h->reader); h->reader = NULL; }
}

static Handle *get_handle(PyObject *capsule) {
    Handle *h = PyCapsule_GetPointer(capsule, capsule_name);
    if (h && (!h->reader || h->close_pending)) { PyErr_SetString(PyExc_ValueError, "native reader is closed"); return NULL; }
    return h;
}
static void destroy(PyObject *capsule) {
    Handle *h = PyCapsule_GetPointer(capsule, capsule_name);
    if (!h) { PyErr_Clear(); return; }
    release_reader(h);
    PyMem_Free(h);
}
static PyObject *open_reader(PyObject *self, PyObject *args) {
    const char *index, *pin, *archive;
    int local;
    if (!PyArg_ParseTuple(args, "sssi", &index, &pin, &archive, &local)) return NULL;
    Handle *h = PyMem_Calloc(1, sizeof(*h));
    if (!h) return PyErr_NoMemory();
    int status = gaia_open(index, pin, archive, local, &h->reader);
    if (status) { PyMem_Free(h); PyErr_Format(PyExc_ValueError, "native open failed (status %d)", status); return NULL; }
    PyObject *capsule = PyCapsule_New(h, capsule_name, destroy);
    if (!capsule) { gaia_close(h->reader); PyMem_Free(h); }
    return capsule;
}
static PyObject *catalog(PyObject *self, PyObject *capsule) {
    Handle *h = get_handle(capsule);
    if (!h) return NULL;
    if (h->live) { PyErr_SetString(PyExc_ValueError,"native catalog has no bulk export"); return NULL; }
    const unsigned char *names, *dirs;
    uint64_t names_len, dirs_len, count;
    gaia_catalog(h->reader, &names, &dirs, &names_len, &dirs_len, &count);
    if (names_len > PY_SSIZE_T_MAX || dirs_len > PY_SSIZE_T_MAX) { PyErr_SetString(PyExc_OverflowError, "catalog too large"); return NULL; }
    PyObject *n = PyBytes_FromStringAndSize((const char *)names, (Py_ssize_t)names_len);
    if (!n) return NULL;
    PyObject *d = PyBytes_FromStringAndSize((const char *)dirs, (Py_ssize_t)dirs_len);
    if (!d) { Py_DECREF(n); return NULL; }
    return Py_BuildValue("NNK", n, d, (unsigned long long)count);
}
static PyObject *read_entry(PyObject *self, PyObject *args) {
    PyObject *capsule;
    unsigned long long row;
    if (!PyArg_ParseTuple(args, "OK", &capsule, &row)) return NULL;
    Handle *h = get_handle(capsule);
    if (!h) return NULL;
    const unsigned char *data;
    uint64_t length;
    int status = gaia_read(h->reader, row, &data, &length);
    if (status) { PyErr_SetString(status == 9 ? PyExc_IndexError : PyExc_ValueError, status == 8 ? "native CRC mismatch" : "native entry out of range"); return NULL; }
    if (length > PY_SSIZE_T_MAX) { PyErr_SetString(PyExc_OverflowError, "entry too large"); return NULL; }
    return PyBytes_FromStringAndSize((const char *)data, (Py_ssize_t)length);
}
static PyObject *close_reader(PyObject *self, PyObject *capsule) {
    Handle *h = PyCapsule_GetPointer(capsule, capsule_name);
    if (!h) return NULL;
    if (h->active_decodes) h->close_pending = 1;
    else release_reader(h);
    Py_RETURN_NONE;
}
/* No mapped pointer escapes this GIL-held call. Returned code owns its data. */
static PyObject *read_code(PyObject *self, PyObject *args) {
    PyObject *capsule;
    unsigned long long row;
    const char *magic, *hash = NULL;
    Py_ssize_t magic_len, hash_len = 0;
    if (!PyArg_ParseTuple(args, "OKy#|y#", &capsule, &row, &magic, &magic_len, &hash, &hash_len)) return NULL;
    if (magic_len != 4 || (hash && hash_len != 8)) {
        PyErr_SetString(PyExc_ValueError, "invalid bytecode identity length"); return NULL;
    }
    Handle *h = get_handle(capsule);
    if (!h) return NULL;
    const unsigned char *data;
    uint64_t length;
    int status = gaia_read(h->reader, row, &data, &length);
    if (status) { PyErr_SetString(status == 9 ? PyExc_IndexError : PyExc_ValueError, status == 8 ? "native CRC mismatch" : "native entry out of range"); return NULL; }
    if (length > PY_SSIZE_T_MAX) { PyErr_SetString(PyExc_OverflowError, "entry too large"); return NULL; }
    if (length < 16 || memcmp(data, magic, 4)) {
        PyErr_SetString(PyExc_ImportError, "invalid/interpreter-incompatible bytecode"); return NULL;
    }
    uint32_t flags = (uint32_t)data[4] | ((uint32_t)data[5] << 8) | ((uint32_t)data[6] << 16) | ((uint32_t)data[7] << 24);
    if ((flags & ~3u) || (hash && (flags != 3 || memcmp(data+8, hash, 8)))) {
        PyErr_SetString(PyExc_ImportError, "bytecode flags/source identity differs"); return NULL;
    }
    /* Audit callbacks/GC finalizers may close this reader reentrantly. Defer
       unmapping until the outermost decoder returns, including failure.
       PyMarshal_ReadObjectFromString emits marshal.loads itself. */
    h->active_decodes++;
    PyObject *code = PyMarshal_ReadObjectFromString((const char *)data+16, (Py_ssize_t)length-16);
    h->active_decodes--;
    if (!h->active_decodes && h->close_pending && h->reader) {
        release_reader(h);
    }
    if (!code) return NULL;
    if (!PyCode_Check(code)) { Py_DECREF(code); PyErr_SetString(PyExc_ImportError, "bytecode payload is not a code object"); return NULL; }
    return code;
}
static PyObject *live_open(PyObject *self, PyObject *args) {
    const char *index,*pin,*archive; int local; unsigned long long budget;
    if (!PyArg_ParseTuple(args,"sssiK",&index,&pin,&archive,&local,&budget)) return NULL;
    Handle *h=PyMem_Calloc(1,sizeof(*h)); if (!h) return PyErr_NoMemory(); h->live=1;
    int status=gaia_live_open(index,pin,archive,local,budget,&h->reader);
    if (status) { PyMem_Free(h); PyErr_Format(status==10 ? PyExc_MemoryError : PyExc_ValueError,"native catalog open failed (status %d)",status); return NULL; }
    PyObject *capsule=PyCapsule_New(h,capsule_name,destroy);
    if (!capsule) { release_reader(h);PyMem_Free(h); } return capsule;
}
static PyObject *mapped_open(PyObject *self,PyObject *args) {
    const char *index,*pin,*archive,*lookup,*lookup_pin;int local;unsigned long long budget;
    if (!PyArg_ParseTuple(args,"sssssiK",&index,&pin,&archive,&lookup,&lookup_pin,&local,&budget)) return NULL;
    Handle *h=PyMem_Calloc(1,sizeof(*h));if (!h) return PyErr_NoMemory();h->live=2;
    int status=gaia_mapped_open(index,pin,archive,lookup,lookup_pin,local,budget,&h->reader);
    if (status) { PyMem_Free(h);PyErr_Format(status==10 ? PyExc_MemoryError : PyExc_ValueError,"mapped catalog open failed (status %d)",status);return NULL; }
    PyObject *capsule=PyCapsule_New(h,capsule_name,destroy);
    if (!capsule) { release_reader(h);PyMem_Free(h); }return capsule;
}
static PyObject *unified_open(PyObject *self,PyObject *args) {
    const char *path,*pin,*index_pin,*archive;int local;unsigned long long budget;
    if (!PyArg_ParseTuple(args,"ssssiK",&path,&pin,&index_pin,&archive,&local,&budget)) return NULL;
    Handle *h=PyMem_Calloc(1,sizeof(*h));if (!h) return PyErr_NoMemory();h->live=3;
    int status=gaia_unified_open(path,pin,index_pin,archive,local,budget,&h->reader);
    if (status) { PyMem_Free(h);PyErr_Format(status==10 ? PyExc_MemoryError : PyExc_ValueError,"unified catalog open failed (status %d)",status);return NULL; }
    PyObject *capsule=PyCapsule_New(h,capsule_name,destroy);
    if (!capsule) { release_reader(h);PyMem_Free(h); }return capsule;
}
static Handle *live_handle(PyObject *capsule) {
    Handle *h=get_handle(capsule);
    if (h && !h->live) { PyErr_SetString(PyExc_ValueError,"requires native catalog"); return NULL; } return h;
}
static PyObject *live_lookup(PyObject *self,PyObject *args) {
    PyObject *capsule;const char *name;int kind;
    if (!PyArg_ParseTuple(args,"Osi",&capsule,&name,&kind)) return NULL;
    Handle *h=live_handle(capsule);if (!h) return NULL;
    return PyLong_FromLongLong(gaia_live_lookup(h->reader,name,kind));
}
static PyObject *live_name(PyObject *self,PyObject *args) {
    PyObject *capsule;unsigned long long row;
    if (!PyArg_ParseTuple(args,"OK",&capsule,&row)) return NULL;
    Handle *h=live_handle(capsule);if (!h) return NULL;
    const unsigned char *dir,*name;uint64_t dl,nl;int32_t pkg;
    if (gaia_live_name(h->reader,row,&dir,&name,&dl,&nl,&pkg)) { PyErr_SetString(PyExc_IndexError,"native row out of range");return NULL; }
    PyObject *a=PyUnicode_DecodeUTF8((const char *)dir,dl,"strict");if (!a) return NULL;
    PyObject *b=PyUnicode_DecodeUTF8((const char *)name,nl,"strict");if (!b) { Py_DECREF(a);return NULL; }
    PyObject *full=PyUnicode_Concat(a,b);Py_DECREF(a);Py_DECREF(b);if (!full) return NULL;
    return Py_BuildValue("NN",full,PyBool_FromLong(pkg));
}
static PyObject *live_stats(PyObject *self,PyObject *capsule) {
    Handle *h=live_handle(capsule);if (!h) return NULL;uint64_t stats[6];gaia_live_stats(h->reader,&stats);
    return Py_BuildValue("KKKKKK",stats[0],stats[1],stats[2],stats[3],stats[4],stats[5]);
}
static PyObject *live_children(PyObject *self,PyObject *args) {
    PyObject *capsule;unsigned long long directory;int kind;int64_t head,count;
    if (!PyArg_ParseTuple(args,"OKi",&capsule,&directory,&kind)) return NULL;
    Handle *h=live_handle(capsule);if (!h) return NULL;
    if (gaia_live_children(h->reader,directory,kind,&head,&count)) { PyErr_SetString(PyExc_IndexError,"native directory out of range");return NULL; }
    return Py_BuildValue("LL",head,count);
}
static PyObject *live_next(PyObject *self,PyObject *args) {
    PyObject *capsule;unsigned long long row;int kind;
    if (!PyArg_ParseTuple(args,"OKi",&capsule,&row,&kind)) return NULL;
    Handle *h=live_handle(capsule);if (!h) return NULL;
    return PyLong_FromLongLong(gaia_live_next(h->reader,row,kind));
}
static PyObject *live_dir_name(PyObject *self,PyObject *args) {
    PyObject *capsule;unsigned long long directory;const unsigned char *name;uint64_t length;
    if (!PyArg_ParseTuple(args,"OK",&capsule,&directory)) return NULL;
    Handle *h=live_handle(capsule);if (!h) return NULL;
    if (gaia_live_dir_name(h->reader,directory,&name,&length)) { PyErr_SetString(PyExc_IndexError,"native directory out of range");return NULL; }
    return PyUnicode_DecodeUTF8((const char *)name,length,"strict");
}
static PyObject *live_subdir(PyObject *self,PyObject *args) {
    PyObject *capsule;unsigned long long parent,cursor;
    if (!PyArg_ParseTuple(args,"OKK",&capsule,&parent,&cursor)) return NULL;
    Handle *h=live_handle(capsule);if (!h) return NULL;
    return PyLong_FromLongLong(gaia_live_subdir(h->reader,parent,cursor));
}
static PyObject *live_export(PyObject *self,PyObject *capsule) {
    Handle *h=live_handle(capsule);if (!h) return NULL;
    if (h->live!=1) { PyErr_SetString(PyExc_ValueError,"requires constructed native catalog");return NULL; }
    const unsigned char *data;uint64_t length;gaia_live_export(h->reader,&data,&length);
    if (length>PY_SSIZE_T_MAX) { PyErr_SetString(PyExc_OverflowError,"export too large");return NULL; }
    return PyBytes_FromStringAndSize((const char *)data,(Py_ssize_t)length);
}
static PyObject *live_phases(PyObject *self,PyObject *capsule) {
    Handle *h=live_handle(capsule);if (!h) return NULL;double phases[3];gaia_live_phases(h->reader,&phases);
    return Py_BuildValue("ddd",phases[0],phases[1],phases[2]);
}
static PyMethodDef methods[] = {
    {"open", open_reader, METH_VARARGS, NULL}, {"catalog", catalog, METH_O, NULL},
    {"read", read_entry, METH_VARARGS, NULL}, {"close", close_reader, METH_O, NULL},
    {"read_code", read_code, METH_VARARGS, NULL},
    {"live_open", live_open, METH_VARARGS, NULL}, {"live_lookup", live_lookup, METH_VARARGS, NULL},
    {"live_name", live_name, METH_VARARGS, NULL}, {"live_stats", live_stats, METH_O, NULL},
    {"live_children", live_children, METH_VARARGS, NULL}, {"live_next", live_next, METH_VARARGS, NULL},
    {"live_dir_name", live_dir_name, METH_VARARGS, NULL},
    {"live_subdir", live_subdir, METH_VARARGS, NULL},
    {"mapped_open", mapped_open, METH_VARARGS, NULL}, {"live_export", live_export, METH_O, NULL},
    {"live_phases", live_phases, METH_O, NULL},
    {"unified_open", unified_open, METH_VARARGS, NULL},
    {NULL, NULL, 0, NULL}
};
static struct PyModuleDef module = { PyModuleDef_HEAD_INIT, "_gaia_native", NULL, -1, methods };
PyMODINIT_FUNC PyInit__gaia_native(void) { return PyModule_Create(&module); }
