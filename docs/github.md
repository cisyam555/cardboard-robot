# 上传 GitHub

本目录是独立项目，原来的购买资料和测试网页在它外面。仅上传本目录，不要在父目录执行 `git add .`。

1. 登录 GitHub，新建名为 `cardboard-robot` 的仓库；公开或私有按个人需要选择。不要勾选自动生成 README、.gitignore 或许可证，避免首次推送出现两个不同的历史。
2. 如果 GitHub 要求启用双重验证，请先在网页中本人完成，并妥善保存恢复码，不要把密码、验证码或恢复码写进仓库。
3. 在本项目目录内执行以下命令，将地址替换成你的真实仓库地址：

```bash
git remote add origin https://github.com/YOUR_USERNAME/cardboard-robot.git
git push -u origin main
```

若本地尚无首次提交，先配置自己的 Git 提交身份，然后执行：

```bash
git add .
git commit -m "feat: 新增纸壳机器人互动固件"
```

GitHub HTTPS 推送使用已配置的凭据管理器或 GitHub CLI 登录；不能使用账号密码代替访问令牌。也可以使用已配置的 SSH。不要把令牌直接写进 remote URL。

之后每次按修改内容提交，再 `git push`。GitHub 用目录展示模块，一个仓库即可容纳正式程序、历史例子和自动测试，无需给每个模块单独建仓库。
