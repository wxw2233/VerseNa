# 固定形状 + 槽位覆盖 UI 实现计划

## T0: CSS 变量 + 默认米哈游形状
Files: `frontend/src/assets/theme-base.css` (新建)
- 定义 11 个 `--ui-*` CSS 变量
- 默认值：米哈游风格（菱形切角、发光边、渐变线）
- App.vue 中 import

## T1+T2: 素材上传器 → 11 槽位 + 删除间距标签
Files: `frontend/src/components/AssetUploader.vue`, `frontend/src/views/SettingsView.vue`
- AssetUploader 改为 11 槽位网格
- 每个槽位：名称 + 预览 + 上传按钮
- SettingsView 删除间距子标签

## T3: 全局 CSS 变量绑定
Files: 遍历所有 .vue 文件
- 替换硬编码样式为 `var(--ui-*)`

Build + tests + commit.
