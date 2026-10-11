// com.pymiere.link — CEP 主脚本
// 引擎启动时加载：把 JSON polyfill + $._pymiere 对象桥装进全局作用域。
// 路径保持纯 ASCII（扩展装在 C:/Program Files/Common Files/Adobe/CEP/extensions/ 下）。

(function () {
    try {
        var self = new File($.fileName);
        var poly = new File(self.parent.fsName + "/ExtendJSON.jsx");
        if (poly.exists) {
            $.evalFile(poly.fsName);
        }
    } catch (e) {
        // 失败不阻塞：面板启动时会用 $.evalFile("C:/prlink/ExtendJSON.jsx") 再注入一次
    }
})();
