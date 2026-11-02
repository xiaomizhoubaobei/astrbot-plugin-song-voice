# 🎵 AstrBot 点歌语音插件（astrbot-plugin-song-voice）

迁移自 Koishi 插件 [koishi-plugin-music-to-voice](https://github.com/sdxcvbot/koishi-plugin-music-to-voice)，
数据来源同为 GD 音乐台 API。

功能：

- 🔍 搜索歌曲并返回歌单
- 📄 上一页 / 下一页翻页
- 🔢 回复序号点歌
- 🎤 可选 ffmpeg 转码后发送语音（aac / wav，silk 回退 wav）
- 🗑 生成提示 / 歌单可自动撤回
- 🎛 面板中可选音源、码率、指令别名等

## 安装

1. 把本仓库放进 AstrBot 的 `data/plugins/` 下，或在 WebUI 插件市场通过仓库地址安装。
2. 安装依赖：`pip install -r requirements.txt`
3. 建议安装 ffmpeg（容器内一般为 `ffmpeg`），否则高码率歌曲可能发不出去。

## 使用

```
点歌 晴天
1              # 选第 1 首
下一页 / 上一页
0              # 退出选择
```

默认触发词为 `点歌`，别名 `听歌`、`music`，均可在配置中修改。

## 工作流程

```
搜索 → 渲染歌单 → 等待序号（默认 45 秒）
     → 取直链（按 999→740→320→192→128 逐级降码率）
     → 需要时下载 + ffmpeg 转码 → 以语音发送
```

发送策略（与 Koishi 版保持一致）：

- 直链可用且码率 < 320：直接以音频文件发送，快
- wma 或码率 ≥ 320：下载后转码，稳
- 未安装 ffmpeg：退化为直接下载文件发送

## 目录结构

```
main.py              插件入口，事件分发
_conf_schema.json    面板配置项
core/config.py       配置解析与默认值
core/api.py          GD 音乐台 API 请求
core/models.py       搜索结果归一化
core/audio.py        ffmpeg 转码
core/session.py      会话状态、歌单渲染
install_gpg_keys.sh  可选：GPG 签名环境一键安装
```

## GPG 签名环境（可选）

仓库根目录附带 `install_gpg_keys.sh`，用于在构建/发布环境里一条命令装好「GPG 密钥导入 + 信任 + git 签名接管」全链路，
让提交签名落在你自己的密钥指纹上，而不是平台章。

```bash
export GPG_KEY="<私钥解锁短语>"          # 必填，未注入脚本直接退出
export GPG_API="https://..."            # 可选，不填走脚本内置的默认分发 API
bash install_gpg_keys.sh
```

脚本特性：

- 幂等：重复执行结果一致，缺 `gnupg` / `curl` / `jq` 时自动安装
- 无 TTY 友好：全程 `--pinentry-mode loopback`，并生成 `/tmp/gpg-wrapper.sh` 作为 `gpg.program`
- 签名接管：有工作树时同时写 local + global，避免旧签名器残留导致不生效
- 自检闭环：真实跑一次 `git commit -S` 并验签，指纹不符就报错退出（不假装成功）

> 注意：`GPG_KEY` 只从环境变量读取，请勿写入脚本或提交到仓库。

## 已知限制

- silk 编码未实现，选择后自动回退 wav
- 高码率（740/999）可能返回 wma，建议开启强制转码
- 部分音源随时可能失效，推荐网易云 / QQ 音乐

## License

MIT
