# file_manager 工具实现计划

**Goal:** 为 agent 添加文件管理工具，分三个阶段安全交付。

## T0: 只读 action + 路径安全 + 审计日志

### Task 1

**Files:**
- Create: `backend/tools/builtin/file_manager.py`
- Modify: `backend/tools/registry.py`

- [ ] FileManagerTool 类，只实现 read/list/search/info 四个 action
- [ ] 路径处理：expanduser → abspath → realpath（校验用）/ 原始路径（操作用）
- [ ] 禁止路径检查（目录型前缀+分隔符，文件型精确匹配，Windows 小写）
- [ ] 所有操作（含只读）都校验硬禁止路径
- [ ] 二进制检测（read 触发，前 8KB 有 null 字节返回 BINARY_FILE_NOT_SUPPORTED）
- [ ] 审计日志写入 data/audit.log
- [ ] 统一返回格式 {success, data/error, message}
- [ ] 注册到 tool_registry
- [ ] 测试 + 提交

## T1: 写入 action + 确认机制 + 信任模式

### Task 2

**Files:**
- Modify: `backend/tools/builtin/file_manager.py`
- Modify: `backend/api/chat.py`
- Modify: `backend/api/config_api.py`

- [ ] 实现 write/find_replace/copy/move/delete 五个 action
- [ ] write: overwrite/append 模式，path 为目录返回 PATH_IS_DIRECTORY
- [ ] find_replace: 全文本全局替换，大文件(>500KB)拒绝，纳入修改类操作
- [ ] copy/move: dst 语义（目录/不存在/已存在），双向安全校验，跨分区 move 降级
- [ ] delete: recursive 参数，默认 false，递归删除前遍历校验所有子项
- [ ] 确认机制：后端返回 confirm 消息（带 request_id），等待前端确认响应
- [ ] 确认超时 60s → CONFIRM_TIMEOUT
- [ ] 信任模式：app_config 存储 file_trust_mode，GET/POST API
- [ ] 敏感路径：主目录下 . 开头的隐藏文件/目录
- [ ] 测试 + 提交

## T2: 前端交互

### Task 3

**Files:**
- Modify: `frontend/src/views/SettingsView.vue`
- Modify: `frontend/src/views/ChatView.vue`

- [ ] 设置页"工具" tab 添加信任模式开关
- [ ] ChatView 收到 confirm 消息时显示模态确认框
- [ ] 确认框显示操作描述 + 文件路径 + 文件/目录总数
- [ ] 点确认发送 confirm_response（带 request_id）
- [ ] 构建 + 提交
