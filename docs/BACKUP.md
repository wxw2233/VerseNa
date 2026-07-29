# 数据备份与恢复

VerseNa 的备份包含：

- 会话、记忆和模型配置数据库
- 上传文件
- 角色、主题和主题包
- 自定义及已安装 Skill

## 创建备份

在项目根目录运行：

```bash
python backend/scripts/backup_user_data.py
```

备份默认写入 `backups/`，并保留最近 10 份。可通过参数调整：

```bash
python backend/scripts/backup_user_data.py --output D:\VerseNaBackups --keep 20
```

脚本使用 SQLite 在线备份 API，因此应用运行时也能生成一致的数据库副本。备份中可能包含 API Key 和私人对话，应保存在可信位置。

## 恢复备份

1. 完全退出 VerseNa。
2. 解压目标 ZIP。
3. 将解压后的目录按原路径覆盖到项目根目录。
4. 重新启动 VerseNa 并检查会话、角色和设置。

恢复前建议先为当前数据再创建一份备份。
