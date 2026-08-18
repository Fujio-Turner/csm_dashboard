"""Slim ctypes wrapper around libcblite Community Edition.

Talks to the Couchbase Lite C API: open a database, collections, JSON
CRUD, SQL++, and value indexes. No Sync Gateway, no vector index.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import platform
from ctypes import (
    POINTER,
    Structure,
    byref,
    c_bool,
    c_double,
    c_int,
    c_int32,
    c_int64,
    c_size_t,
    c_uint,
    c_uint8,
    c_uint32,
    c_uint64,
    c_void_p,
    cdll,
)
from pathlib import Path

from .errors import CouchbaseLiteError, CouchbaseLiteNotAvailable, CouchbaseLiteNotFound


class FLSlice(Structure):
    _fields_ = [("buf", c_void_p), ("size", c_size_t)]


FLString = FLSlice
FLSliceResult = FLSlice


class CBLError(Structure):
    _fields_ = [
        ("domain", c_uint8),
        ("code", c_int),
        ("internal_info", c_uint),
    ]


class CBLDatabaseConfiguration(Structure):
    _fields_ = [
        ("directory", FLSlice),
        ("fullSync", c_bool),
    ]


class CBLValueIndexConfiguration(Structure):
    _fields_ = [
        ("expressionLanguage", c_uint32),
        ("expressions", FLSlice),
        ("where", FLSlice),
    ]


class CBLFullTextIndexConfiguration(Structure):
    _fields_ = [
        ("expressionLanguage", c_uint32),
        ("expressions", FLSlice),
        ("ignoreAccents", c_bool),
        ("language", FLSlice),
        ("where", FLSlice),
    ]


_NULL_SLICE = FLSlice(None, 0)
FL_UNDEFINED = -1
FL_NULL = 0
FL_BOOL = 1
FL_NUMBER = 2
FL_STRING = 3
CBL_N1QL_LANGUAGE = 1


def _to_flslice(s: str | None, keepalive: list) -> FLSlice:
    if s is None:
        return _NULL_SLICE
    b = s.encode("utf-8")
    keepalive.append(b)
    return FLSlice(ctypes.cast(ctypes.c_char_p(b), c_void_p), len(b))


def _from_flslice(sl: FLSlice) -> str | None:
    if not sl.buf or sl.size == 0:
        return None
    return ctypes.string_at(sl.buf, sl.size).decode("utf-8")


def _from_flsliceresult(sl: FLSliceResult, lib) -> str | None:
    val = _from_flslice(sl)
    if sl.buf:
        lib._FLBuf_Release(sl.buf)
    return val


def _load_library() -> ctypes.CDLL:
    explicit = os.environ.get("CBLITE_LIB_PATH")
    if explicit:
        try:
            return cdll.LoadLibrary(explicit)
        except OSError as exc:
            raise CouchbaseLiteNotAvailable(
                f"Cannot load libcblite from CBLITE_LIB_PATH={explicit}: {exc}"
            ) from exc

    system = platform.system()
    candidates: list[str] = []
    if system == "Darwin":
        candidates = [
            "libcblite.dylib",
            "/opt/homebrew/lib/libcblite.dylib",
            "/usr/local/lib/libcblite.dylib",
        ]
    elif system == "Windows":
        candidates = ["cblite.dll"]
    else:
        candidates = [
            "libcblite.so.4",
            "libcblite.so.3",
            "libcblite.so",
            "/opt/cblite/lib/x86_64-linux-gnu/libcblite.so",
            "/opt/cblite/lib/libcblite.so",
        ]

    for name in candidates:
        try:
            return cdll.LoadLibrary(name)
        except OSError:
            continue

    found = ctypes.util.find_library("cblite")
    if found:
        try:
            return cdll.LoadLibrary(found)
        except OSError:
            pass

    hint = "\n  brew install --cask libcblite-community" if system == "Darwin" else ""
    raise CouchbaseLiteNotAvailable("libcblite shared library not found." + hint)


def _bind(lib: ctypes.CDLL) -> ctypes.CDLL:
    lib.CBL_Release.argtypes = [c_void_p]
    lib.CBL_Release.restype = None
    lib._FLBuf_Release.argtypes = [c_void_p]
    lib._FLBuf_Release.restype = None
    lib.CBLError_Message.argtypes = [POINTER(CBLError)]
    lib.CBLError_Message.restype = FLSliceResult
    lib.CBLDatabase_Open.argtypes = [FLSlice, POINTER(CBLDatabaseConfiguration), POINTER(CBLError)]
    lib.CBLDatabase_Open.restype = c_void_p
    lib.CBLDatabase_Close.argtypes = [c_void_p, POINTER(CBLError)]
    lib.CBLDatabase_Close.restype = c_bool
    lib.CBLDatabase_BeginTransaction.argtypes = [c_void_p, POINTER(CBLError)]
    lib.CBLDatabase_BeginTransaction.restype = c_bool
    lib.CBLDatabase_EndTransaction.argtypes = [c_void_p, c_bool, POINTER(CBLError)]
    lib.CBLDatabase_EndTransaction.restype = c_bool
    lib.CBLDatabase_CreateCollection.argtypes = [c_void_p, FLSlice, FLSlice, POINTER(CBLError)]
    lib.CBLDatabase_CreateCollection.restype = c_void_p
    lib.CBLCollection_Count.argtypes = [c_void_p]
    lib.CBLCollection_Count.restype = c_uint64
    lib.CBLCollection_PurgeDocumentByID.argtypes = [c_void_p, FLSlice, POINTER(CBLError)]
    lib.CBLCollection_PurgeDocumentByID.restype = c_bool
    if hasattr(lib, "CBLCollection_SetDocumentExpiration"):
        lib.CBLCollection_SetDocumentExpiration.argtypes = [
            c_void_p,
            FLSlice,
            c_int64,
            POINTER(CBLError),
        ]
        lib.CBLCollection_SetDocumentExpiration.restype = c_bool
    lib.CBLDocument_CreateWithID.argtypes = [FLSlice]
    lib.CBLDocument_CreateWithID.restype = c_void_p
    lib.CBLDocument_SetJSON.argtypes = [c_void_p, FLSlice, POINTER(CBLError)]
    lib.CBLDocument_SetJSON.restype = c_bool
    lib.CBLDocument_CreateJSON.argtypes = [c_void_p]
    lib.CBLDocument_CreateJSON.restype = FLSliceResult
    lib.CBLCollection_SaveDocument.argtypes = [c_void_p, c_void_p, POINTER(CBLError)]
    lib.CBLCollection_SaveDocument.restype = c_bool
    lib.CBLCollection_GetDocument.argtypes = [c_void_p, FLSlice, POINTER(CBLError)]
    lib.CBLCollection_GetDocument.restype = c_void_p
    lib.CBLDatabase_CreateQuery.argtypes = [
        c_void_p,
        c_uint32,
        FLSlice,
        POINTER(c_int),
        POINTER(CBLError),
    ]
    lib.CBLDatabase_CreateQuery.restype = c_void_p
    lib.CBLQuery_Execute.argtypes = [c_void_p, POINTER(CBLError)]
    lib.CBLQuery_Execute.restype = c_void_p
    lib.CBLResultSet_Next.argtypes = [c_void_p]
    lib.CBLResultSet_Next.restype = c_bool
    lib.CBLResultSet_ValueAtIndex.argtypes = [c_void_p, c_uint]
    lib.CBLResultSet_ValueAtIndex.restype = c_void_p
    lib.CBLQuery_ColumnCount.argtypes = [c_void_p]
    lib.CBLQuery_ColumnCount.restype = c_uint
    lib.CBLQuery_ColumnName.argtypes = [c_void_p, c_uint]
    lib.CBLQuery_ColumnName.restype = FLSlice
    lib.CBLQuery_SetParameters.argtypes = [c_void_p, c_void_p]
    lib.CBLQuery_SetParameters.restype = None
    lib.FLDoc_FromJSON.argtypes = [FLSlice, POINTER(CBLError)]
    lib.FLDoc_FromJSON.restype = c_void_p
    lib.FLDoc_GetRoot.argtypes = [c_void_p]
    lib.FLDoc_GetRoot.restype = c_void_p
    lib.FLDoc_Release.argtypes = [c_void_p]
    lib.FLDoc_Release.restype = None
    lib.FLValue_GetType.argtypes = [c_void_p]
    lib.FLValue_GetType.restype = c_int32
    lib.FLValue_AsBool.argtypes = [c_void_p]
    lib.FLValue_AsBool.restype = c_bool
    lib.FLValue_AsInt.argtypes = [c_void_p]
    lib.FLValue_AsInt.restype = c_int64
    lib.FLValue_AsDouble.argtypes = [c_void_p]
    lib.FLValue_AsDouble.restype = c_double
    lib.FLValue_AsString.argtypes = [c_void_p]
    lib.FLValue_AsString.restype = FLSlice
    lib.FLValue_ToJSON.argtypes = [c_void_p]
    lib.FLValue_ToJSON.restype = FLSliceResult
    lib.CBLCollection_CreateValueIndex.argtypes = [
        c_void_p,
        FLSlice,
        CBLValueIndexConfiguration,
        POINTER(CBLError),
    ]
    lib.CBLCollection_CreateValueIndex.restype = c_bool
    lib.CBLCollection_CreateFullTextIndex.argtypes = [
        c_void_p,
        FLSlice,
        CBLFullTextIndexConfiguration,
        POINTER(CBLError),
    ]
    lib.CBLCollection_CreateFullTextIndex.restype = c_bool
    if hasattr(lib, "CBLCollection_DeleteIndex"):
        lib.CBLCollection_DeleteIndex.argtypes = [c_void_p, FLSlice, POINTER(CBLError)]
        lib.CBLCollection_DeleteIndex.restype = c_bool
    return lib


class CBL:
    _cached_lib: ctypes.CDLL | None = None

    @classmethod
    def _get_lib(cls) -> ctypes.CDLL:
        if cls._cached_lib is None:
            cls._cached_lib = _bind(_load_library())
        return cls._cached_lib

    @property
    def _lib(self) -> ctypes.CDLL:
        return self._get_lib()

    def __init__(self, db_path: str) -> None:
        p = Path(db_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == ".cblite2":
            db_name = p.stem
            db_dir = str(p.parent.resolve())
        else:
            db_name = p.name
            db_dir = str(p.parent.resolve())

        self._keepalive: list[bytes] = []
        name_sl = _to_flslice(db_name, self._keepalive)
        dir_sl = _to_flslice(db_dir, self._keepalive)
        cfg = CBLDatabaseConfiguration()
        cfg.directory = dir_sl
        cfg.fullSync = False
        err = CBLError()
        self._db = self._lib.CBLDatabase_Open(name_sl, byref(cfg), byref(err))
        self._check(err, "Failed to open database")
        if not self._db:
            raise CouchbaseLiteError("CBLDatabase_Open returned NULL")

    def close(self) -> None:
        if getattr(self, "_db", None):
            err = CBLError()
            self._lib.CBLDatabase_Close(self._db, byref(err))
            self._lib.CBL_Release(self._db)
            self._db = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _check(self, err: CBLError, context: str = "") -> None:
        if err.code != 0:
            msg_sl = self._lib.CBLError_Message(byref(err))
            msg = _from_flsliceresult(msg_sl, self._lib) or "unknown error"
            full = f"{context}: {msg}" if context else msg
            if err.domain == 1 and err.code == 404:
                raise CouchbaseLiteNotFound(full, err.domain, err.code)
            raise CouchbaseLiteError(full, err.domain, err.code)

    def get_or_create_collection(self, name: str, scope: str = "_default") -> c_void_p:
        ka: list[bytes] = []
        err = CBLError()
        col = self._lib.CBLDatabase_CreateCollection(
            self._db, _to_flslice(name, ka), _to_flslice(scope, ka), byref(err)
        )
        self._check(err, f"create collection {scope}.{name}")
        if not col:
            raise CouchbaseLiteError(f"Collection {scope}.{name} is NULL")
        return col

    def collection_count(self, collection: c_void_p) -> int:
        return int(self._lib.CBLCollection_Count(collection))

    def save_document_json(self, collection: c_void_p, doc_id: str, json_str: str) -> None:
        ka: list[bytes] = []
        doc = self._lib.CBLDocument_CreateWithID(_to_flslice(doc_id, ka))
        if not doc:
            raise CouchbaseLiteError("CBLDocument_CreateWithID returned NULL")
        try:
            err = CBLError()
            ok = self._lib.CBLDocument_SetJSON(doc, _to_flslice(json_str, ka), byref(err))
            self._check(err, "SetJSON")
            if not ok:
                raise CouchbaseLiteError("SetJSON returned false")
            err2 = CBLError()
            ok2 = self._lib.CBLCollection_SaveDocument(collection, doc, byref(err2))
            self._check(err2, "SaveDocument")
            if not ok2:
                raise CouchbaseLiteError("SaveDocument returned false")
        finally:
            self._lib.CBL_Release(doc)

    def get_document_json(self, collection: c_void_p, doc_id: str) -> str | None:
        ka: list[bytes] = []
        err = CBLError()
        doc = self._lib.CBLCollection_GetDocument(collection, _to_flslice(doc_id, ka), byref(err))
        if err.code != 0:
            if err.domain == 1 and err.code == 404:
                return None
            self._check(err, "GetDocument")
        if not doc:
            return None
        try:
            sl = self._lib.CBLDocument_CreateJSON(doc)
            return _from_flsliceresult(sl, self._lib)
        finally:
            self._lib.CBL_Release(doc)

    def set_document_expiration(self, collection: c_void_p, doc_id: str, when_ms: int) -> None:
        fn = getattr(self._lib, "CBLCollection_SetDocumentExpiration", None)
        if fn is None:
            return
        ka: list[bytes] = []
        err = CBLError()
        ok = fn(collection, _to_flslice(doc_id, ka), c_int64(int(when_ms)), byref(err))
        self._check(err, "SetDocumentExpiration")
        if not ok:
            raise CouchbaseLiteError("SetDocumentExpiration returned false")

    def purge_document(self, collection: c_void_p, doc_id: str) -> None:
        ka: list[bytes] = []
        err = CBLError()
        self._lib.CBLCollection_PurgeDocumentByID(collection, _to_flslice(doc_id, ka), byref(err))
        if err.code != 0 and not (err.domain == 1 and err.code == 404):
            self._check(err, "PurgeDocument")

    def begin_transaction(self) -> None:
        err = CBLError()
        ok = self._lib.CBLDatabase_BeginTransaction(self._db, byref(err))
        self._check(err, "BeginTransaction")
        if not ok:
            raise CouchbaseLiteError("BeginTransaction returned false")

    def end_transaction(self, commit: bool = True) -> None:
        err = CBLError()
        ok = self._lib.CBLDatabase_EndTransaction(self._db, commit, byref(err))
        self._check(err, "EndTransaction")
        if not ok:
            raise CouchbaseLiteError("EndTransaction returned false")

    def create_value_index(self, collection: c_void_p, index_name: str, expressions: str) -> None:
        ka: list[bytes] = []
        cfg = CBLValueIndexConfiguration()
        cfg.expressionLanguage = CBL_N1QL_LANGUAGE
        cfg.expressions = _to_flslice(expressions, ka)
        cfg.where = _NULL_SLICE
        err = CBLError()
        ok = self._lib.CBLCollection_CreateValueIndex(
            collection, _to_flslice(index_name, ka), cfg, byref(err)
        )
        if err.code != 0:
            msg_sl = self._lib.CBLError_Message(byref(err))
            msg = (_from_flsliceresult(msg_sl, self._lib) or "").lower()
            if "already" in msg or "exist" in msg:
                return
            self._check(err, f"CreateValueIndex {index_name}")
        if not ok and err.code == 0:
            return

    def create_full_text_index(
        self,
        collection: c_void_p,
        index_name: str,
        expressions: str,
        language: str = "en",
    ) -> None:
        ka: list[bytes] = []
        cfg = CBLFullTextIndexConfiguration()
        cfg.expressionLanguage = CBL_N1QL_LANGUAGE
        cfg.expressions = _to_flslice(expressions, ka)
        cfg.ignoreAccents = False
        cfg.language = _to_flslice(language, ka)
        cfg.where = _NULL_SLICE
        err = CBLError()
        ok = self._lib.CBLCollection_CreateFullTextIndex(
            collection, _to_flslice(index_name, ka), cfg, byref(err)
        )
        if err.code != 0:
            msg_sl = self._lib.CBLError_Message(byref(err))
            msg = (_from_flsliceresult(msg_sl, self._lib) or "").lower()
            if "already" in msg or "exist" in msg:
                return
            self._check(err, f"CreateFullTextIndex {index_name}")
        if not ok and err.code == 0:
            return

    def delete_index(self, collection: c_void_p, index_name: str) -> None:
        fn = getattr(self._lib, "CBLCollection_DeleteIndex", None)
        if not fn:
            return
        ka: list[bytes] = []
        err = CBLError()
        ok = fn(collection, _to_flslice(index_name, ka), byref(err))
        if err.code != 0:
            msg_sl = self._lib.CBLError_Message(byref(err))
            msg = (_from_flsliceresult(msg_sl, self._lib) or "").lower()
            if "not found" in msg or "no such" in msg or "exist" in msg:
                return
            self._check(err, f"DeleteIndex {index_name}")
        if not ok and err.code == 0:
            return

    def _flvalue_to_python(self, val: c_void_p):
        if not val:
            return None
        vtype = self._lib.FLValue_GetType(val)
        if vtype in (FL_UNDEFINED, FL_NULL):
            return None
        if vtype == FL_BOOL:
            return self._lib.FLValue_AsBool(val)
        if vtype == FL_NUMBER:
            d = self._lib.FLValue_AsDouble(val)
            i = self._lib.FLValue_AsInt(val)
            return i if d == float(i) else d
        if vtype == FL_STRING:
            return _from_flslice(self._lib.FLValue_AsString(val))
        sl = self._lib.FLValue_ToJSON(val)
        raw = _from_flsliceresult(sl, self._lib)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def execute_query(self, sql: str, params_json: str | None = None) -> list[dict]:
        ka: list[bytes] = []
        err_pos = c_int(-1)
        err = CBLError()
        query = self._lib.CBLDatabase_CreateQuery(
            self._db, CBL_N1QL_LANGUAGE, _to_flslice(sql, ka), byref(err_pos), byref(err)
        )
        self._check(err, f"CreateQuery (pos {err_pos.value})")
        if not query:
            raise CouchbaseLiteError(f"CreateQuery NULL (pos {err_pos.value})")
        try:
            if params_json is not None:
                perr = CBLError()
                doc = self._lib.FLDoc_FromJSON(_to_flslice(params_json, ka), byref(perr))
                self._check(perr, "FLDoc_FromJSON")
                if doc:
                    try:
                        root = self._lib.FLDoc_GetRoot(doc)
                        if root:
                            self._lib.CBLQuery_SetParameters(query, root)
                    finally:
                        self._lib.FLDoc_Release(doc)
            err2 = CBLError()
            rs = self._lib.CBLQuery_Execute(query, byref(err2))
            self._check(err2, "Query_Execute")
            if not rs:
                raise CouchbaseLiteError("Query_Execute returned NULL")
            try:
                ncols = self._lib.CBLQuery_ColumnCount(query)
                names = []
                for i in range(ncols):
                    names.append(_from_flslice(self._lib.CBLQuery_ColumnName(query, i)) or f"col{i}")
                rows: list[dict] = []
                while self._lib.CBLResultSet_Next(rs):
                    row = {}
                    for i, name in enumerate(names):
                        row[name] = self._flvalue_to_python(self._lib.CBLResultSet_ValueAtIndex(rs, i))
                    rows.append(row)
                return rows
            finally:
                self._lib.CBL_Release(rs)
        finally:
            self._lib.CBL_Release(query)
