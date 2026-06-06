# AGFSSkill — 运维巡检技能集

跨平台系统运维巡检技能集合，覆盖 **Windows** 和 **Linux** 系统，一键采集 30+ 项系统数据，生成专业巡检报告。

## 📦 技能列表

| 技能 | 路径 | 说明 |
|---|---|---|
| **one-click-inspection** | `skills/one-click-inspection/` | 一键运维巡检，支持 HTML / JSON / Markdown 输出 |

## 🚀 快速开始

```bash
# Windows 巡检
python skills/one-click-inspection/scripts/win_inspection_html.py -f html

# Linux 巡检
chmod +x skills/one-click-inspection/scripts/linux_inspect.sh
sudo ./skills/one-click-inspection/scripts/linux_inspect.sh --fast
```

## 📋 技能详情

### one-click-inspection

跨平台一键运维巡检工具，采集 30+ 项系统数据，生成蓝白侧边栏风格的专业 HTML 巡检报告。

**采集能力（Windows）：**

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

### 输出格式

所有脚本支持统一的命令行接口：

| 选项 | 说明 |
|---|---|
| `-o FILE` | 指定报告输出路径 |
| `-f FORMAT` | 输出格式：`html`（默认）、`json`、`md` |
| `-v` | 详细日志 |
| `-h` | 显示帮助信息 |

## 📁 目录结构

```
agfsskill/
├── README.md                          # 本文件
└── skills/
    └── one-click-inspection/
        ├── SKILL.md                   # 技能说明
        ├── assets/
        │   └── report-preview.html    # 报告样张
        └── scripts/
            ├── win_inspection_html.py # Windows 巡检脚本 (Python)
            └── linux_inspect.sh       # Linux 巡检脚本 (Bash, v2.5)
```

## ⚙️ 环境要求

- **Windows**: Python 3.10+（兼容至 3.13），推荐以管理员权限运行
- **Linux**: Bash 4.0+，建议以 root/sudo 权限运行

## 📄 许可证

MIT
