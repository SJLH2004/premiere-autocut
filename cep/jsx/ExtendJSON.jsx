// ExtendJSON.jsx
// Minimal JSON stringify polyfill for ExtendScript (ES3) + pymiere helpers.
// Injected into Premiere's global scope by the Pymiere Link CEP panel.

(function () {

    var escapable = /[\\\"\x00-\x1f\x7f-\x9f\u00ad\u0600-\u0604\u070f\u17b4\u17b5\u200c-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]/g;

    var meta = {
        '\b': '\\b',
        '\t': '\\t',
        '\n': '\\n',
        '\f': '\\f',
        '\r': '\\r',
        '"': '\\"',
        '\\': '\\\\'
    };

    function quote(s) {
        escapable.lastIndex = 0;
        if (escapable.test(s)) {
            return '"' + s.replace(escapable, function (a) {
                var c = meta[a];
                if (typeof c === 'string') { return c; }
                return '\\u' + ('0000' + a.charCodeAt(0).toString(16)).slice(-4);
            }) + '"';
        }
        return '"' + s + '"';
    }

    function has(o, k) {
        return Object.prototype.hasOwnProperty.call(o, k);
    }

    // ES3：Array.prototype.indexOf 不存在（实测报 seen.indexOf is not a function）
    function inArray(arr, v) {
        for (var n = 0; n < arr.length; n++) {
            if (arr[n] === v) { return true; }
        }
        return false;
    }

    // 坑：ExtendScript 里普通字面量对象 {} 也有 .reflect（Object.prototype 上），
    // 所以必须把 reflect.name === 'Object' 排除掉，否则 {"isObject":...} 会被
    // 当成宿主对象再包一层，objectType 变成 "Object"。
    function isHostObject(v) {
        try {
            if (typeof v !== 'object' || v === null) { return false; }
            if (v instanceof Array) { return false; }
            if (!v.reflect || !v.reflect.name) { return false; }
            if (v.reflect.name === 'Object') { return false; }
            return true;
        } catch (e) {
            return false;
        }
    }

    function walk(value, replacer, seen) {
        var i, v, parts, k, raw, t;

        if (value === null || value === undefined) { return 'null'; }

        t = typeof value;
        if (t === 'string') { return quote(value); }
        if (t === 'number') { return isFinite(value) ? String(value) : 'null'; }
        if (t === 'boolean') { return String(value); }
        if (t !== 'object') { return 'null'; }

        // circular reference guard
        if (inArray(seen, value)) { return 'null'; }
        seen.push(value);

        try {
            if (value instanceof Array) {
                parts = [];
                for (i = 0; i < value.length; i++) {
                    v = replacer ? replacer(String(i), value[i]) : value[i];
                    if (v === undefined) { continue; }
                    parts.push(walk(v, replacer, seen));
                }
                seen.pop();
                return '[' + parts.join(',') + ']';
            }

            // plain object or host object
            parts = [];
            for (k in value) {
                if (!has(value, k)) { continue; }
                raw = value[k];
                if (typeof raw === 'function' || raw === undefined) { continue; }
                v = replacer ? replacer(k, raw) : raw;
                if (v === undefined) { continue; }
                parts.push(quote(k) + ':' + walk(v, replacer, seen));
            }
            seen.pop();
            return '{' + parts.join(',') + '}';
        } catch (e) {
            return 'null';
        }
    }

    function stringify(value, replacer, space) {
        var seen = [];
        var root = replacer ? replacer('', value) : value;
        if (root === undefined) { return undefined; }
        return walk(root, replacer, seen);
    }

    // Signature keeps a 4th argument because pymiere calls stringify(v, replacer, 0, 1).
    $.global.ExtendJSON = {
        stringify: function (value, replacer, space, unused) {
            return stringify(value, replacer, space);
        },
        parse: function (text) {
            return eval('(' + text + ')');
        }
    };

    // Replacer pymiere uses when serializing values that may carry host objects.
    // Functions and unserialisable internals are dropped; Premiere API objects are
    // collapsed to a reference the python side can keep track of.
    $.global.internal_variables_replacer = function (key, value) {
        if (typeof value === 'function') { return undefined; }
        if (value === undefined) { return undefined; }
        if (isHostObject(value)) {
            // 嵌套的宿主对象也要登记进 $._pymiere，并带上 pymiereId，
            // 否则 python 端 _format_object_to_py() 取 obj["pymiereId"] 会 KeyError
            var nid;
            try { nid = $.global._pymiere.generateId(); } catch (e) { return undefined; }
            $.global._pymiere[nid] = value;
            return { isObject: true, objectType: value.reflect.name, pymiereId: nid };
        }
        return value;
    };

    // ------------------------------------------------------------------
    // $._pymiere : pymiere 的对象桥
    // pymiere/core.py 的 _eval_script_returning_object() 会执行：
    //     var newPymiereId = $._pymiere.generateId();
    //     $._pymiere[newPymiereId] = tmp;        // 宿主对象按 id 存起来
    // 之后所有属性/方法调用都走 $._pymiere['<id>']...
    // 没有这个对象 -> 整条链路报 "EvalScript error."
    // ------------------------------------------------------------------
    // 注意：实测 $.global !== $，而 pymiere 用的是 $._pymiere，
    // 所以必须挂在 $ 本身（$.global 只影响裸标识符解析）
    var P = ($._pymiere && typeof $._pymiere === 'object') ? $._pymiere
          : ((typeof $.global !== 'undefined' && $.global && typeof $.global._pymiere === 'object') ? $.global._pymiere : null);
    if (!P) { P = {}; }
    $._pymiere = P;
    try { $.global._pymiere = P; } catch (e) {}

    if (!(P.generatedIds instanceof Array)) {
        P.generatedIds = [];
    }

    if (typeof P.generateId !== 'function') {
        P.generateId = function () {
            var n = 0, s;
            do {
                s = String(n);
                n++;
            } while (inArray(P.generatedIds, s));
            P.generatedIds.push(s);
            return s;
        };
    }

    // 释放：pymiere 在 Python 对象被 GC 时会删掉引用
    if (typeof P.release !== 'function') {
        P.release = function (id) {
            try { delete P[id]; } catch (e) {}
            for (var i = 0; i < P.generatedIds.length; i++) {
                if (P.generatedIds[i] === id) { P.generatedIds.splice(i, 1); break; }
            }
            return true;
        };
    }

    // ----- ES5 垫片：ExtendScript 是 ES3，pymiere 的 __del__ 会用 indexOf -----
    if (typeof Array.prototype.indexOf !== 'function') {
        Array.prototype.indexOf = function (v, from) {
            var i = from ? Number(from) : 0;
            if (i < 0) { i = 0; }
            for (; i < this.length; i++) { if (this[i] === v) { return i; } }
            return -1;
        };
    }
    if (typeof Array.prototype.lastIndexOf !== 'function') {
        Array.prototype.lastIndexOf = function (v, from) {
            var i = (from === undefined) ? this.length - 1 : Number(from);
            if (i >= this.length) { i = this.length - 1; }
            for (; i >= 0; i--) { if (this[i] === v) { return i; } }
            return -1;
        };
    }
    if (typeof Array.prototype.forEach !== 'function') {
        Array.prototype.forEach = function (fn, ctx) {
            for (var i = 0; i < this.length; i++) { if (i in this) { fn.call(ctx, this[i], i, this); } }
        };
    }
    if (typeof Array.prototype.map !== 'function') {
        Array.prototype.map = function (fn, ctx) {
            var out = [];
            for (var i = 0; i < this.length; i++) { if (i in this) { out.push(fn.call(ctx, this[i], i, this)); } }
            return out;
        };
    }
    if (typeof Array.prototype.filter !== 'function') {
        Array.prototype.filter = function (fn, ctx) {
            var out = [];
            for (var i = 0; i < this.length; i++) { if (i in this && fn.call(ctx, this[i], i, this)) { out.push(this[i]); } }
            return out;
        };
    }
    if (typeof String.prototype.trim !== 'function') {
        String.prototype.trim = function () {
            return String(this).replace(/^[\s\xA0]+/, '').replace(/[\s\xA0]+$/, '');
        };
    }

    // convenience
    $.global.pymiereReady = true;

})();
