# BainPoison

基于 Flask、Selenium 和 Chrome 的网页答题自动化实验。程序从本地题库读取题目，按配置在浏览器中填写资料、答题并记录结果。仓库保留了当时的页面快照、运行日志和 Windows 打包文件；这些文件不代表目前的目标网站仍保持相同结构或允许自动提交。

## 仓库内容

- `app.py`：本地控制页面、自动化流程及日志接口。
- `index.html`：配置与启动界面。
- `quiz_bank.json`：运行时读取的本地题库。
- `requirements.txt`、`app.spec`：Python 依赖与 PyInstaller 打包配置。

## 访问方式

`python app.py` 默认只监听 `127.0.0.1:5000`，不启动公网隧道。需要远程访问时，先设置环境变量 `BAINPOISON_ENABLE_TUNNEL=1` 和 `BAINPOISON_PASSWORD`，再启动程序。远程页面和全部 API 使用同一组 HTTP Basic 凭据：用户名为 `admin`，密码为你设置的口令。请勿把口令写入仓库、命令行参数或公开截图。

```powershell
$env:BAINPOISON_ENABLE_TUNNEL = '1'
$env:BAINPOISON_PASSWORD = '<自行设置的长口令>'
python app.py
```

即使有访问口令，公网隧道也只应在需要时开启；临时 URL 不是保密凭据。已发布的旧版本没有这些保护，不能用旧版程序或旧版打包文件开放公网访问。

当前版本已将本地配置、日志、第三方页面快照和旧打包产物移出 Git 跟踪，并用 `.gitignore` 避免再次提交。旧提交的历史仍可能包含个人资料或不安全的可执行文件；本次提交不会抹去历史，公开展示前仍应逐项检查历史记录，并确认目标网站的使用规则。

## 运行前检查

源码依赖列于 `requirements.txt`，另需本机 Chrome。使用前应检查目标网站的使用规则和本机配置内容。仓库历史中的个人资料仍需单独处理；本次访问控制修改不会从 Git 历史或已打包的可执行文件中移除它们。
