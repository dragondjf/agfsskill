# 常见错误排查指南

## 1. 模型下载失败

**错误信息：**
```
embedding error: request error: https://huggingface.co/...: Connection Failed
embedding error: daemon returned an empty response
```

**原因：** 无法连接到 HuggingFace 下载 `multilingual-e5-small` 模型（约 465MB）。

**解决：**
```bash
# 使用国内镜像
set HF_ENDPOINT=https://hf-mirror.com
sqlite-graphrag init

# 或清理缓存后重试
sqlite-graphrag cache clear-models --yes
set HF_ENDPOINT=https://hf-mirror.com
sqlite-graphrag init
```

## 2. Daemon 返回空响应

**错误信息：**
```
embedding error: daemon returned an empty response
```

**原因：** 模型文件不完整或 `.lock` 文件残留。

**解决：**
```bash
# 1. 清理所有 sqlite-graphrag 进程
# 2. 清理锁文件（位于 %LOCALAPPDATA%\sqlite-graphrag\cache\models\...\blobs\*.lock）
# 3. 清理模型缓存
sqlite-graphrag cache clear-models --yes
# 4. 重新 init
sqlite-graphrag init
```

## 3. Header Content-Range is missing

**错误信息：**
```
embedding error: Header Content-Range is missing
```

**原因：** 模型文件下载不完整（部分文件缺失）。

**解决：** 清理缓存后重新下载完整模型文件。

## 4. 无效的 --type

**错误信息：**
```
error: invalid value 'tool' for '--type <TYPE>'
```

**原因：** `remember` 的 `--type` 只接受 9 种值。

**解决：** 使用有效值：`user`, `feedback`, `project`, `reference`, `decision`, `incident`, `skill`, `document`, `note`。

## 5. 图谱为空

**现象：** `graph --format mermaid` 输出空图。

**原因：** NER 默认关闭，没有提取实体关系。

**解决：** 写入时启用 NER：
```bash
sqlite-graphrag remember --name test --type note \
  --description "测试" --body "..." \
  --enable-ner --gliner-variant int8
```

## 6. 二进制升级后 daemon 不匹配

**现象：** 升级二进制后命令报错。

**原因：** 旧 daemon 进程仍在运行，与新二进制版本不匹配。

**解决：** 杀掉旧 daemon 进程后重试，新版本会自动检测并重启 daemon。

## 7. 数据库文件过大

**现象：** graphrag.sqlite 体积增长过快。

**解决：**
```bash
# 回收空间
sqlite-graphrag vacuum

# 优化
sqlite-graphrag optimize
```

## 8. 并发写入冲突

**现象：** 多个进程同时写入时报错。

**原因：** SQLite 单进程架构限制。

**解决：** 使用 `--wait-lock <SECONDS>` 等待锁释放，或串行化写入操作。

## 9. 记忆写入超时

**现象：** `remember` 命令长时间无响应。

**原因：** 首次使用需要下载模型，或 daemon 启动较慢。

**解决：** 先执行 `init` 预下载模型，后续操作会更快。
