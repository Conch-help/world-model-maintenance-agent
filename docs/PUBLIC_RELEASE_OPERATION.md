# 代码仓库与公开发布操作卡

## A. 代码仓库发布

### 方式 1：上传 ZIP

1. 在 GitHub/Gitee 新建空仓库，建议名称 `world-model-maintenance-agent`。
2. 不要勾选自动生成 README、LICENSE 或 .gitignore。
3. 上传 `代码仓库上传包-github.zip` 解压后的全部文件，或直接使用仓库导入功能。
4. 发布后检查仓库首页是否显示 README、MIT License、提交号和交付材料。

### 方式 2：导入 Git Bundle

```powershell
git clone 代码仓库-git-bundle.bundle world-model-maintenance-agent
cd world-model-maintenance-agent
git remote add origin <你的空仓库地址>
git push -u origin main
```

当前本地提交：

```text
a4e7d0b Initial public release: world-model maintenance agent U068
```

## B. 公开内容发布

推荐平台：知乎、CSDN、公众号或 B站。

1. 使用 `公开发布内容-可直接复制.md` 正文。
2. 封面使用 `04-public-cover.png`。
3. 代码仓库已填写为 https://gitee.com/ZzX729183/world-model-maintenance-agent；视频链接：https://www.bilibili.com/video/BV1Jspj66Eed；发布日期：2026-10-11。
4. 发布后记录平台、链接、截图和日期。
5. 截图至少包含页面标题、发布日期和项目图。

## C. 发布后回填

- 代码仓库：〔链接〕
- 视频主链接：https://www.bilibili.com/video/BV1Jspj66Eed
- 备用视频链接：〔可选〕
- 公开内容平台：〔平台〕
- 公开内容链接：〔链接〕
- 发布日期：2026-10-09

## D. 发布前检查

- [ ] 仓库不含 `.secrets/`、`.agh/`、API Key、Token 和 Cookie
- [ ] 仓库不含原始 `agh_real_session.json`
- [ ] 仓库不含学号、出生年月、家庭地址和手机号
- [ ] 公开内容不把 TEP 写成真实 DCS
- [ ] 公开内容不把虚拟 Modbus 写成真实 PLC
