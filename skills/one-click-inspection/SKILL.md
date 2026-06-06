---
name: one-click-inspection
description: 跨平台一键运维巡检工具，覆盖 Windows 和 Linux 系统。采集主机基本信息、硬件资源、网络配置、安全审计、用户权限、进程服务、启动项、软件清单、事件日志、Docker 容器、NPU/AI 推理、电源散热等 30+ 项系统数据，生成蓝白侧边栏风格的专业 HTML 巡检报告。当用户要求"巡检""体检""系统检查""运维检查""inspection""系统检测""一键体检"时触发。
---

# 一键运维巡检技能

## 概述

跨平台一键运维巡检工具，覆盖 Windows 和 Linux 系统。采集 30+ 项系统数据，生成蓝白侧边栏风格的专业 HTML 巡检报告。

## 目录结构

```
one-click-inspection/
├── SKILL.md                    # 本技能说明
├── assets/
│   └── report-preview.html     # 报告样张
└── scripts/
    ├── win_inspection_html.py  # Windows 巡检脚本
    └── linux_inspect.sh        # Linux 巡检脚本 (v2.5)
```

## 脚本说明

### Windows 巡检脚本 (`win_inspection_html.py`)

**功能**：Windows 系统一键巡检，采集 30+ 项系统数据，生成蓝白侧边栏风格的 HTML 报告。

**采集能力**：
1. **主机基本信息**：主机名、操作系统版本、架构、主板、BIOS、安全启动、许可证状态、运行时间
2. **硬件资源状态**：CPU 型号/核心/线程/频率/负载、内存总量/使用率/内存条信息、磁盘容量/使用率/物理磁盘健康、GPU/驱动
3. **网络配置与连接**：适配器/IP/网关/DNS/流量统计/连接状态/监听端口(含知识库)/共享文件夹
4. **安全配置审计**：防火墙/RDP/BitLocker/Defender/密码策略/系统更新/审计策略/时间同步
5. **用户与权限**：本地用户列表、管理员组成员
6. **进程与服务分析**：进程总数、运行中服务、内存占用 Top 10(含 PID)
7. **启动项与计划任务**：注册表启动项、非微软计划任务
8. **已安装软件**：软件名称/版本/发布者/安装日期
9. **事件日志分析**：系统日志+应用日志错误聚合(按 EventID+Source 分组)
10. **Docker 与容器**：Docker 版本、容器总数、运行中容器详情
11. **NPU 与 AI 推理**：NPU 加速器、CUDA GPU、AI 推理进程(含 PID/内存)、推理服务端口
12. **电源与散热**：电池状态、温度传感器、风扇转速、电源计划
13. **风险评估与建议**：综合风险等级、问题列表、安全建议

**报告样式**：蓝白侧边栏风格（--c-side-bg: #0f172a, --c-primary: #1976d2），固定左侧导航栏，滚动高亮，响应式布局，支持打印样式。

**运行方式**：
```bash
python win_inspection_html.py
```

输出文件：`System_Inspection_Report_YYYYMMDD_HHMMSS.html`

### Linux 巡检脚本 (`linux_inspect.sh`)

**版本**：v2.5 | **文件大小**：~97 KB | **行数**：~2,220 行

**功能**：Linux 服务器一键深度巡检，覆盖 18+ 大类系统指标，生成蓝白侧边栏风格的专业 HTML 报告（与 Windows 版报告样式一致）。

**适用发行版**：CentOS 7/8, RHEL, Ubuntu, Debian, Kylin, UOS, SUSE, Arch, Alpine, Gentoo 等主流发行版（通过多源 OS 检测自动识别）。

**采集能力**：
1. **主机基本信息**：主机名/FQDN、操作系统发行版/版本/内核/架构、IP 地址(三级 fallback)、运行时间、当前登录用户、时区(四源检测)、语言环境、虚拟化类型(物理机/VMware/KVM/QEMU/Xen/Hyper-V)
2. **CPU 与负载**：型号/核心/插槽数、使用率(/proc/stat 采样 200ms → top fallback)、负载(1/5/15 分钟)、运行中进程数、CPU 占用 Top 10
3. **内存与 Swap**：总量/可用/使用率、Swap 总量/使用率、hugepages 配置
4. **磁盘存储**：分区挂载/总容量/已用/可用/使用率、Inode 使用率、文件系统类型、物理磁盘列表(型号/容量/转速)
5. **大文件扫描**：可配置阈值(默认 100M)、最近修改大文件(默认 7 天)、搜索路径 /var /home /opt /usr/local
6. **文件描述符**：系统级限制/当前使用量/使用率、进程级 Top 5
7. **网络配置**：物理适配器/速率、IPv4/IPv6 地址、默认网关(三级 fallback)、DNS 服务器、监听端口(含进程/PID)、连接统计(ESTABLISHED/TIME_WAIT/CLOSE_WAIT)
8. **进程分析**：进程/线程总数、内存占用 Top 10、僵尸进程检测
9. **服务状态**：运行中/启用服务列表、关键服务(sshd/crond/rsyslog/ntpd/chronyd)专项检查、systemd/sysvinit 双轨检测
10. **Docker 与容器**：Docker/Podman 自动检测、容器总数/运行中/停止、容器详情(镜像/端口/状态)
11. **定时任务**：所有用户的 crontab 列表、系统定时任务
12. **安全检查**：SELinux 状态、防火墙状态(firewalld/ufw/nftables/iptables/SuSEfirewall2 五源识别)、SSH 配置(端口/root 登录/密码认证)、密码策略(/etc/login.defs + /etc/pam.d)、sudoers 配置、可疑 SUID 文件、弱权限文件、最近登录失败记录、known_hosts 检查
13. **内核参数**：关键 sysctl 参数(网络/安全/内存)、内核模块列表
14. **系统更新**：包管理器更新检查(apt/yum/dnf/zypper/pacman/apk 全支持)、可升级包数量、最近安装的更新
15. **SSL 证书**：扫描常见路径的证书到期时间（可配置告警阈值，默认 30 天）
16. **系统日志**：dmesg 内核日志(含 journalctl -k fallback)、关键错误/硬件错误/OOM 检测、最近登录日志
17. **总体建议**：短期/中期/长期优化建议卡片、综合风险等级评估

**报告样式**：与 Windows 版一致的蓝白侧边栏风格（--c-side-bg: #0f172a, --c-primary: #1976d2），固定左侧导航栏，滚动高亮，响应式布局，支持打印样式。新增推荐卡片（短期/中期/长期建议）、免责声明区块、锚点高亮动画。

**运行方式**：
```bash
chmod +x linux_inspect.sh
./linux_inspect.sh                    # 默认完整巡检
./linux_inspect.sh --fast             # 快速模式（跳过大文件/更新/SSL 扫描）
./linux_inspect.sh -f json -o /tmp/r.json  # 输出 JSON 格式
./linux_inspect.sh -v                 # 详细日志模式
```

**命令行选项**：
| 选项 | 说明 |
|------|------|
| `-o FILE` | 指定报告输出路径 |
| `-f FORMAT` | 输出格式：html（默认）或 json |
| `-v, --verbose` | 详细日志（含 debug 信息） |
| `-q, --quiet` | 静默模式（仅错误输出） |
| `--no-large-file-scan` | 跳过大文件扫描 |
| `--skip-update-check` | 跳过包管理器联网检查（最慢的单步） |
| `--skip-ssl-check` | 跳过 SSL 证书扫描 |
| `--fast` | 快速模式 = 上面三个 skip 全开 |
| `-h, --help` | 显示帮助信息 |

**环境变量**：`INSPECT_REPORT_DIR` 自定义报告目录（默认 `/tmp/inspect_report`）

**退出码**：0=正常（无警告/无严重），1=有警告，2=有严重告警/脚本错误

**输出文件**：`inspect_<hostname>_<YYYYMMDD_HHMMSS>.html`（默认路径 `/tmp/inspect_report/`）

**兼容性特性**：
- Bash 4+ 要求（使用 here-string、关联数组等特性）
- systemd / sysvinit 双轨服务检测
- `hostname -I` → `ip addr` → `ifconfig` 三级 IP fallback
- `ip route` → `netstat -rn` → `route -n` 三级网关 fallback
- `dmesg` → `journalctl -k` 内核日志 fallback（应对 kernel.dmesg_restrict=1）
- 防火墙五源识别：firewalld → ufw → nftables → iptables → SuSEfirewall2
- 时区四源检测：timedatectl → /etc/timezone → readlink /etc/localtime → /etc/sysconfig/clock
- 容器引擎自动识别：docker → podman
- CPU 使用率快速采样：/proc/stat 200ms 间隔（省去 top/mpstat/vmstat 各 1s fallback）

## 使用流程

1. **Windows 巡检**：
   ```bash
   cd scripts/
   python win_inspection_html.py
   ```

2. **Linux 巡检**：
   ```bash
   cd scripts/
   chmod +x linux_inspect.sh
   ./linux_inspect.sh
   # 快速模式（推荐日常巡检）：
   ./linux_inspect.sh --fast
   ```

3. **查看报告**：用浏览器打开生成的 HTML 文件即可查看完整巡检报告。

## 注意事项

- Windows 巡检需要管理员权限以获得完整数据（温度传感器、审计策略等）
- Linux 巡检建议以 root 或 sudo 权限运行以获得完整数据（温度传感器、审计策略、dmesg 等）
- Docker 检测需要 Docker 已安装并在 PATH 中
- NPU 检测支持 Intel NPU、NVIDIA GPU（CUDA）等加速器
- Linux 脚本的 `--fast` 模式适合日常巡检，完整模式适合深度巡检
- Linux 脚本输出路径可通过 `INSPECT_REPORT_DIR` 环境变量自定义
