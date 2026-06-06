# AGFSSkill — AI 技能集

AI 驱动的运维与测试技能集合，覆盖 **系统巡检** 和 **视频测试** 两大场景。

## 📦 技能列表

| 技能 | 路径 | 说明 |
|---|---|---|
| **one-click-inspection** | `skills/one-click-inspection/` | 一键运维巡检（Win/Linux），30+ 项系统数据，HTML/JSON/MD 输出 |
| **video-test-gen** | `skills/video-test-gen/` | 操作视频自动生成测试用例，输出 Excel/Word/测试记录 |

## 🚀 快速开始

```bash
# 一键运维巡检 —— Windows
python skills/one-click-inspection/scripts/win_inspection_html.py -f html

# 一键运维巡检 —— Linux
chmod +x skills/one-click-inspection/scripts/linux_inspect.sh
sudo ./skills/one-click-inspection/scripts/linux_inspect.sh --fast

# 视频测试用例生成
pip install opencv-python scikit-image pandas xlsxwriter python-docx openai
python skills/video-test-gen/scripts/pipeline.py <video_path> <output_dir> --api-key sk-xxx
```

## 📋 技能详情

### one-click-inspection

跨平台一键运维巡检工具，采集 30+ 项系统数据，生成蓝白侧边栏风格的专业 HTML 巡检报告。

**采集能力（Windows，13 大模块）：**

| # | 模块 | 采集项 |
|---|---|---|
| 一 | 主机基本信息 | 主机名、OS、架构、主板、BIOS、安全启动、许可证、运行时间 |
| 二 | 硬件资源 | CPU/内存/磁盘/GPU 状态、内存条信息、物理磁盘健康 |
| 三 | 网络配置 | 适配器、IP、网关、DNS、流量、连接状态、监听端口、共享文件夹 |
| 四 | 安全审计 | 防火墙、RDP、BitLocker、Defender、密码策略、系统更新、审计策略 |
| 五 | 用户与权限 | 本地用户、管理员组 |
| 六 | 进程与服务 | 进程数、运行中服务、内存占用 Top 10 |
| 七 | 启动项与任务 | 注册表启动项、非微软计划任务 |
| 八 | 已安装软件 | 名称/版本/发布者/安装日期 |
| 九 | 事件日志 | 系统日志+应用日志错误聚合 |
| 十 | Docker | 版本、容器数、运行中容器详情 |
| 十一 | NPU & AI | NPU 加速器、AI 推理进程/端口 |
| 十二 | 电源散热 | 电池、温度、风扇、电源计划 |
| 十三 | 风险评估 | 综合风险等级、问题列表、建议 |

**采集能力（Linux，18+ 大类）：**
主机信息、CPU 与负载、内存与 Swap、磁盘存储、大文件扫描、文件描述符、网络配置、进程分析、服务状态、Docker/Podman 容器、定时任务、安全检查、内核参数、系统更新、SSL 证书、系统日志、总体建议

**统一命令行接口：**

| 选项 | 说明 |
|---|---|
| `-o FILE` | 指定报告输出路径 |
| `-f FORMAT` | 输出格式：`html`（默认）、`json`、`md` |
| `-v` | 详细日志 |
| `-h` | 显示帮助信息 |

---

### video-test-gen

从操作录屏视频自动转化为结构化测试用例，输出格式化 Excel、图文 Word 和模板格式测试记录。

**流程：**

```
视频 → 关键帧提取 → [二次筛选] → AI分析 → 用例合并 → 步骤补全 → Excel + Word + 测试记录
```

**模块脚本：**

| 脚本 | 功能 |
|---|---|
| `extract_keyframes.py` | 从视频中提取关键帧（基于直方图差异 + 场景检测） |
| `analyze_frames.py` | 多模态 AI 分析关键帧，生成结构化测试步骤 |
| `merge_test_cases.py` | 合并相邻场景用例，智能补全前置条件/预期结果 |
| `generate_reports.py` | 输出格式化 Excel + 图文 Word 报告 |
| `generate_test_records.py` | 按模板生成标准化测试记录文档 |
| `pipeline.py` | 全流程一键执行，支持断点续跑 |

**依赖：**
```bash
pip install opencv-python scikit-image pandas xlsxwriter python-docx openai
```

---

## 📁 目录结构

```
agfsskill/
├── README.md
└── skills/
    ├── one-click-inspection/
    │   ├── SKILL.md
    │   ├── assets/
    │   │   └── report-preview.html
    │   └── scripts/
    │       ├── win_inspection_html.py
    │       └── linux_inspect.sh
    └── video-test-gen/
        ├── SKILL.md
        ├── references/
        │   └── test_records_template.docx
        └── scripts/
            ├── analyze_frames.py
            ├── extract_keyframes.py
            ├── generate_reports.py
            ├── generate_test_records.py
            ├── merge_test_cases.py
            └── pipeline.py
```

## ⚙️ 环境要求

| 技能 | 环境 |
|---|---|
| one-click-inspection | Windows: Python 3.10+，推荐管理员权限；Linux: Bash 4.0+，推荐 root/sudo |
| video-test-gen | Python 3.9+，需安装 opencv-python / pandas / xlsxwriter / python-docx / openai |

## 📄 许可证

MIT
