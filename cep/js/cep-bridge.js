/**
 * cep-bridge.js — 极简 CEP 宿主桥（替代 Adobe 的 CSInterface.js）
 *
 * 为什么需要这个文件
 * ------------------
 * Adobe 随 CEP SDK 分发的 CSInterface.js 是专有文件，头部明确写着
 * 「distribution of it requires the prior written permission of Adobe」，
 * 因此不能随开源项目一起分发。
 *
 * 但本面板只用到它的 3 个接口：
 *     new CSInterface()
 *     cs.getSystemPath(SystemPath.EXTENSION)
 *     cs.evalScript(code, callback)
 * 而这三者底层都是 CEP 运行时注入到页面里的 window.__adobe_cep__（公开 API）。
 * 所以这里用干净实现替代，不再需要那个专有文件。
 *
 * 许可：MIT（本文件为本项目原创，不含任何 Adobe 代码）
 */
(function (global) {
    'use strict';

    function host() {
        return global.__adobe_cep__ || null;
    }

    // ---- SystemPath 枚举（CEP API 的常量值，非代码）----
    var SystemPath = {
        USER_DATA: 'userData',
        COMMON_FILES: 'commonFiles',
        MY_DOCUMENTS: 'myDocuments',
        APPLICATION: 'application',
        EXTENSION: 'extension',
        HOST_APPLICATION: 'hostApplication'
    };

    /**
     * CSInterface 的最小替代实现。
     * 接口名称与 Adobe 版本保持一致，便于与既有代码互换。
     */
    function CSInterface() {}

    /** 是否运行在 CEP 宿主里（在普通浏览器打开时为 false） */
    CSInterface.prototype.isHostPresent = function () {
        return !!host();
    };

    /**
     * 取系统路径。返回值与 CSInterface.getSystemPath 一致：
     * 通常形如 file:///C:/path/to/x，调用方自行归一化。
     */
    CSInterface.prototype.getSystemPath = function (pathType) {
        var h = host();
        if (h && typeof h.getSystemPath === 'function') {
            return h.getSystemPath(pathType);
        }
        // 退化路径：EXTENSION 可用 location 推导（CEP 面板本身是 file:// 页面）
        if (pathType === SystemPath.EXTENSION) {
            var p = String(global.location && global.location.pathname || '');
            var m = p.match(/^(?:file:\/\/\/)?(.*)\/index\.html$/i);
            if (m) return 'file:///' + m[1];
            return p;
        }
        return '';
    };

    /**
     * 在 ExtendScript 引擎里执行代码，结果通过回调返回字符串。
     * 语法错误或引擎未就绪时，宿主会返回 "EvalScript error."。
     */
    CSInterface.prototype.evalScript = function (script, callback) {
        var h = host();
        if (!h || typeof h.evalScript !== 'function') {
            if (typeof callback === 'function') {
                callback('EvalScript error.');
            }
            return;
        }
        if (typeof callback === 'function') {
            h.evalScript(String(script), callback);
            return;
        }
        h.evalScript(String(script));
    };

    /** 宿主环境信息；非 CEP 环境返回空对象 */
    CSInterface.prototype.getHostEnvironment = function () {
        var h = host();
        if (h && typeof h.getHostEnvironment === 'function') {
            try {
                return JSON.parse(h.getHostEnvironment());
            } catch (e) {
                return {};
            }
        }
        return {};
    };

    CSInterface.prototype.getApplicationID = function () {
        var h = host();
        return h && typeof h.getApplicationID === 'function' ? h.getApplicationID() : '';
    };

    // ---- 导出 ----
    global.SystemPath = SystemPath;
    global.CSInterface = CSInterface;
    global.CEPBridge = { SystemPath: SystemPath, CSInterface: CSInterface };
})(this);
