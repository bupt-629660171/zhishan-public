---
name: zhishan-release
description: Use when publishing 知源食养 / 知源智膳 to the public — deploying the Streamlit app, exporting a clean open-source repo, pushing to GitHub, or diagnosing a failed push/deploy. Encodes the pre-publish privacy sweep, the fresh-clone verification loop, the export→push procedure, GitHub connectivity workarounds (DNS hijack, SSH over 443, Windows OpenSSH), Streamlit Cloud specifics, and the release checklist.
whenToUse: 要开源、要发版、要部署 Demo、要推 GitHub，或者推送/部署报错时。
---

# 知源食养 · 发布与部署

发布是唯一会**把内部东西暴露给外人**的动作。这一步的默认心态是：**先假设仓库里有不该给的东西**。

## 0. 三条铁律

1. **现有仓库不要直接公开**——历史里有照片、姓名、密码时，`git log` 一样能看到。
2. **发布前必须做一次全新克隆验证**——不是"我机器上能跑"，是"空目录能跑"。
3. **部署失败先看数据，不看代码**——多数线上事故是缺库、缺依赖、缺 secrets。

## 1. 发布前隐私清单（逐项打勾）

```powershell
# a) 姓名 / 手机 / 邮箱
git grep -n -E '1[3-9][0-9]{9}|[\w.]+@[\w-]+\.[a-z]{2,}' -- .
# b) 本机路径
git grep -n 'C:\\Users' -- .
# c) 图片（只应剩设计预览图）
git ls-files | Select-String '\.(jpg|jpeg|png)$'
# d) 数据库与密钥
git ls-files | Select-String 'food\.db|\.env$|secrets'
```

**重点排查三类容易被忽略的**：

| 类型 | 典型 | 处理 |
|---|---|---|
| 含他人的照片 | 食堂菜单照里有同学 | 移出版本库，来源改文字记录 |
| 工具配置目录 | `design/.edge`、`.chrome`、`.vscode` | `git rm -r --cached` + gitignore |
| 数据库文件 | `food.db` 里有审核人名 | 不入库，改由 `init_db.py` 生成 |

## 2. 全新克隆验证（必做）

```powershell
python scripts/export_public.py        # 输出 dist/zhishan-public，自检姓名/照片
# 复制到空目录，模拟别人 clone
python init_db.py
python -m unittest discover -s tests
python tools.py gate
# 再删掉 food.db 直接起页面，验证冷启动
Remove-Item food.db*
streamlit run app.py
```

三步全过才算"能发布"。**这一步抓到过真 bug**：`init_db` 原先依赖已存在的 `food.db`，空目录直接 `no such table: Dish`。

## 3. 导出与推送

```powershell
python scripts/export_public.py        # 只复制 git 跟踪的文件
cd dist/zhishan-public
git init
git config user.name  "你的GitHub用户名"
git config user.email "你的ID@users.noreply.github.com"
git add -A
git commit -m "知源食养 v1.0.0"
git remote add origin git@github.com:<user>/<repo>.git
git branch -M main
git push -u origin main
```

**必须先配 `user.name/email`**，否则 `git commit` 直接失败；没有 commit 就会出现
`src refspec main does not match any`——这个报错的含义是"本地没有提交"，不是网络问题。

## 4. GitHub 连不上时的排障顺序

1. **先分清是 DNS 还是端口**：`Test-NetConnection github.com -Port 443`
2. **DNS 被劫持**（返回 `127.0.0.1` 或异常 IP）：常见于校园 VPN 客户端（深信服等）。
   先试 `ssh.github.com:443`——它通常能通。
3. **改走 SSH over 443**：`~/.ssh/config`
   ```
   Host github.com
     HostName ssh.github.com
     Port 443
     User git
     IdentityFile ~/.ssh/id_ed25519
     StrictHostKeyChecking no
     UserKnownHostsFile NUL
   ```
   `StrictHostKeyChecking no` 必加：沙箱/无写权限时 `known_hosts` 写不进去，SSH 会卡在交互确认上直到超时。
4. **用 Windows 自带 OpenSSH**，不要用 Git 附带的 MSYS 版：
   ```powershell
   $env:GIT_SSH='C:\Windows\System32\OpenSSH\ssh.exe'
   ```
   MSYS 版会 `couldn't create signal pipe, Win32 error 5`。
5. **不要设 `GIT_SSH_COMMAND`**——它会让 git 调 `sh.exe`，在受限环境里同样失败。
6. 全都不行再考虑：Gitee 中转、网页上传 zip、手机热点。

## 5. Streamlit Cloud 部署要点

- 主文件 `app.py`；依赖 `requirements.txt`（`pandas` 随 streamlit 自带，`dotenv` 必须 try/except 包裹）。
- **数据库不能入库**，因此在 `app.py` 启动时自动初始化：

  ```python
  if not engine.DATABASE_PATH.exists():
      import init_db; init_db.main()
  ```

  这段必须放在第一个 `st.*` 调用之前，且失败时只 `st.warning` 不阻塞。
- 免费实例会休眠，首次访问需唤醒 30 秒；若停在登录页，是应用被设为私有。
- 健康数据不落库、不采集身份，避免 PIPL 敏感个人信息问题。

## 6. 发版检查清单

- [ ] 隐私四查全过
- [ ] 全新目录 init → 单测 → gate 全绿
- [ ] 冷启动（删库）页面能自建
- [ ] 仓库是 Public，LICENSE / CONTRIBUTING / CI 都在
- [ ] Actions 的 `gate` 为绿
- [ ] Demo 链接写进 README
- [ ] README 不含"未审核/草案"这类已过时的免责表述
