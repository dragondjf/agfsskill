# -*- coding: utf-8 -*-
"""
Windows 系统一键巡检脚本
采集 30+ 项系统数据，生成蓝白侧边栏风格的专业 HTML 巡检报告
"""

import subprocess, datetime, json, os, sys, re, base64
from typing import Dict, List, Any
import html as html_mod

def run_command(cmd: str, timeout: int = 30) -> Dict:
    """执行系统命令，返回 {'success': bool, 'stdout': str, 'stderr': str}"""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, encoding='gbk', errors='replace', timeout=timeout)
        return {'success': r.returncode == 0, 'stdout': r.stdout.strip(), 'stderr': r.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {'success': False, 'stdout': '', 'stderr': 'timeout'}
    except Exception as e:
        return {'success': False, 'stdout': '', 'stderr': str(e)}

def ps(script_block: str) -> str:
    """执行 PowerShell 命令（Base64编码避免引号冲突），返回 stdout"""
    encoded = base64.b64encode(script_block.encode('utf-16le')).decode()
    r = run_command(f'powershell -NoProfile -EncodedCommand {encoded}')
    return r['stdout'] if r['success'] else ''


def collect_all() -> Dict:
    """采集所有系统数据"""
    d: Dict[str, Any] = {}

    # 1. 主机基本信息
    d['hostname'] = ps('$e=Get-CimInstance Win32_ComputerSystem;Write-Output $e.Name')
    d['os'] = ps('(Get-CimInstance Win32_OperatingSystem).Caption')
    d['arch'] = ps('$e=Get-CimInstance Win32_ComputerSystem;Write-Output $e.SystemType')
    d['user'] = ps('$e=Get-CimInstance Win32_ComputerSystem;Write-Output $e.UserName')
    d['motherboard'] = ps('$e=Get-CimInstance Win32_BaseBoard;Write-Output "$($e.Manufacturer) $($e.Product)"')
    d['bios'] = ps('$e=Get-CimInstance Win32_BIOS;Write-Output "$($e.Manufacturer) $($e.SMBIOSBIOSVersion) $($e.ReleaseDate.Split(\"T\")[0])"')
    d['uptime'] = ps('$os=Get-CimInstance Win32_OperatingSystem;$up=(Get-Date)-($os.LastBootUpTime);\"{0}天 {1}小时 {2}分钟\"-f $up.Days,$up.Hours,$up.Minutes')
    d['secure_boot'] = ps('Confirm-SecureBootUEFI 2>$null;if($?){if(Confirm-SecureBootUEFI){\"已启用\"}else{\"未启用\"}}else{\"不支持/不可用\"}')

    # 许可证状态
    lic = ps('$s=Get-CimInstance SoftwareLicensingProduct -Filter \"ApplicationID=\'55c92734-d682-4d71-983e-d6ec3f16059f\' AND PartialProductKey IS NOT NULL\";Write-Output "$($s.Name)|$($s.LicenseStatus)"')
    if lic and '|' in lic:
        lp = lic.split('|')
        status_map = {'0':'未授权','1':'已授权','2':'OOB Grace','3':'OOT Grace','4':'非正版 Grace','5':'通知','6':'已扩展'}
        d['license_status'] = status_map.get(lp[1], lp[1])
        d['license_type'] = 'KMS' if 'KMS' in lp[0] else 'MAK' if 'MAK' in lp[0] else 'Retail'
    else:
        d['license_status'] = '未授权'
        d['license_type'] = '未知'

    # 2. 硬件资源
    d['cpu_name'] = ps('$e=Get-CimInstance Win32_Processor -First 1;Write-Output $e.Name')
    d['cpu_cores'] = ps('$e=Get-CimInstance Win32_Processor -First 1;Write-Output $e.NumberOfCores')
    d['cpu_threads'] = ps('$e=Get-CimInstance Win32_Processor -First 1;Write-Output $e.NumberOfLogicalProcessors')
    d['cpu_freq'] = ps('$e=Get-CimInstance Win32_Processor -First 1;Write-Output $e.MaxClockSpeed')
    d['cpu_load'] = ps('$e=Get-CimInstance Win32_Processor -First 1;Write-Output $e.LoadPercentage')
    if not d['cpu_load']:
        d['cpu_load'] = ps('(Get-WmiObject -Class Win32_Processor -Property LoadPercentage).LoadPercentage')

    mem = ps('$e=Get-CimInstance Win32_OperatingSystem;Write-Output "$([math]::Round($e.TotalVisibleMemorySize/1MB,2))|$([math]::Round(($e.TotalVisibleMemorySize-$e.FreePhysicalMemory)/1MB,2))|$([math]::Round($e.FreePhysicalMemory/1MB,2))"')
    if mem and '|' in mem:
        mp = mem.split('|')
        d['mem_total'] = float(mp[0])
        d['mem_used'] = float(mp[1])
        d['mem_free'] = float(mp[2])
    else:
        d['mem_total'] = d['mem_used'] = d['mem_free'] = 0
    d['mem_pct'] = round(d['mem_used'] / d['mem_total'] * 100, 1) if d['mem_total'] > 0 else 0

    # 内存条信息
    mem_chips_raw = ps('Get-CimInstance Win32_PhysicalMemory|ForEach-Object{$m=$_.Manufacturer.Trim();$c=[math]::Round($_.Capacity/1GB,0);$s=$_.Speed;$p=$_.PartNumber.Trim();Write-Output "$m|${c}GB|${s}MHz|$p"}')
    d['mem_chips'] = [line.strip() for line in (mem_chips_raw.split('\n') if mem_chips_raw else []) if line.strip()]

    # 磁盘
    disks_raw = ps('Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3"|ForEach-Object{$p=[math]::Round(($_.Size-$_.FreeSpace)/$_.Size*100,1);Write-Output "$($_.DeviceID)|$($_.VolumeName)|$([math]::Round($_.Size/1GB,0))|$([math]::Round(($_.Size-$_.FreeSpace)/1GB,0))|$([math]::Round($_.FreeSpace/1GB,0))|$p"}')
    d['disks'] = []
    for line in (disks_raw.split('\n') if disks_raw else []):
        p = line.strip().split('|')
        if len(p) >= 6:
            d['disks'].append({'drive': p[0], 'label': p[1], 'total': p[2], 'used': p[3], 'free': p[4], 'pct': p[5]})

    # 物理磁盘
    pd_raw = ps('Get-CimInstance Win32_DiskDrive|ForEach-Object{$s=[math]::Round($_.Size/1GB,0);Write-Output "$($_.Model)|$($_.MediaType)|${s}GB|$($_.InterfaceType)|$($_.Status)"}')
    d['physical_disks'] = []
    for line in (pd_raw.split('\n') if pd_raw else []):
        p = line.strip().split('|')
        if len(p) >= 5:
            d['physical_disks'].append({'name': p[0], 'type': p[1], 'size': p[2], 'bus': p[3], 'health': p[4]})

    # GPU
    d['gpu'] = ps('$e=Get-CimInstance Win32_VideoController -First 1;Write-Output $e.Name')
    d['gpu_driver'] = ps('$e=Get-CimInstance Win32_VideoController -First 1;Write-Output $e.DriverVersion')
    d['unsigned_drivers'] = ps('Get-WindowsDriver -Online -EA SilentlyContinue|Where-Object{$_.DriverSignature -eq $false}|Measure-Object|Select-Object -ExpandProperty Count')

    # 3. 网络
    adapters_raw = ps('Get-NetAdapter -Physical -EA SilentlyContinue|ForEach-Object{Write-Output "$($_.Name)|$($_.Status)|$($_.LinkSpeed)|$($_.MacAddress)"}')
    d['net_adapters'] = []
    for line in (adapters_raw.split('\n') if adapters_raw else []):
        p = line.strip().split('|')
        if len(p) >= 4:
            d['net_adapters'].append({'name': p[0], 'status': p[1], 'speed': p[2], 'mac': p[3]})

    ip_raw = ps('Get-NetIPAddress -AddressFamily IPv4 -EA SilentlyContinue|Where-Object{$_.InterfaceAlias -notlike \"Loopback*\" -and $_.IPAddress -ne \"0.0.0.0\"}|ForEach-Object{Write-Output \"$($_.InterfaceAlias)|$($_.IPAddress)|$($_.PrefixLength)|$($_.PrefixOrigin)\"}')
    d['ipv4_addrs'] = []
    for line in (ip_raw.split('\n') if ip_raw else []):
        p = line.strip().split('|')
        if len(p) >= 4:
            d['ipv4_addrs'].append({'iface': p[0], 'ip': p[1], 'prefix': p[2], 'origin': p[3]})

    d['gateway'] = ps('(Get-NetRoute -DestinationPrefix \"0.0.0.0/0\" -EA SilentlyContinue|Select-Object -First 1).NextHop')
    d['dns'] = ps('(Get-DnsClientServerAddress -AddressFamily IPv4 -EA SilentlyContinue|Select-Object -First 1).ServerAddresses -join \", \"')

    net_stat = ps('$n=Get-NetAdapterStatistics -EA SilentlyContinue|Select-Object -First 1;if($n){\"$($n.ReceivedBytes)|$($n.SentBytes)\"}')
    if net_stat and '|' in net_stat:
        ns = net_stat.split('|')
        d['net_rx'] = f'{int(ns[0])//1048576} MB' if len(ns) > 0 else 'N/A'
        d['net_tx'] = f'{int(ns[1])//1048576} MB' if len(ns) > 1 else 'N/A'
    else:
        d['net_rx'] = d['net_tx'] = 'N/A'

    conn_raw = ps('$c=netstat -n|Select-String -Pattern \"TCP|UDP\";$est=($c|Select-String \"ESTABLISHED\").Count;$lis=($c|Select-String \"LISTENING\").Count;$tw=($c|Select-String \"TIME_WAIT\").Count;Write-Output \"$est|$lis|$tw\"')
    if conn_raw and '|' in conn_raw:
        cp = conn_raw.split('|')
        d['conn_established'] = cp[0] if len(cp) > 0 else 0
        d['conn_listening'] = cp[1] if len(cp) > 1 else 0
        d['conn_timewait'] = cp[2] if len(cp) > 2 else 0
    else:
        d['conn_established'] = d['conn_listening'] = d['conn_timewait'] = 0

    # 监听端口
    port_raw = ps('$p=netstat -ano|Select-String \"LISTENING\";$r=@();$p|ForEach-Object{$_ -match \":(\\d+)\\s+.*?(\\d+)$\"|Out-Null;$port=$Matches[1];$pid=$Matches[2];$proc=(Get-Process -Id $pid -EA SilentlyContinue).ProcessName;if(!$proc){$proc=\"-\"};$r+=[PSCustomObject]@{Port=$port;PID=$pid;Process=$proc}};$r|Group-Object Port,Process|ForEach-Object{$_|Select-Object -First 1}|Sort-Object Port|ForEach-Object{Write-Output \"$($_.Port)|$($_.Process)|ALL\"}')
    d['listen_ports'] = []
    port_kb = {
        '21':'FTP','22':'SSH','23':'Telnet','25':'SMTP','53':'DNS','80':'HTTP','110':'POP3','135':'RPC','139':'NetBIOS','143':'IMAP',
        '389':'LDAP','443':'HTTPS','445':'SMB','465':'SMTPS','500':'IPSec','514':'Syslog','587':'SMTP Submission','636':'LDAPS',
        '993':'IMAPS','995':'POP3S','1080':'SOCKS','1433':'MSSQL','1521':'Oracle DB','2049':'NFS','2375':'Docker(未加密)','2376':'Docker(TLS)',
        '3306':'MySQL','3389':'RDP','5432':'PostgreSQL','5672':'AMQP','5900':'VNC','5985':'WinRM HTTP','5986':'WinRM HTTPS',
        '6379':'Redis','6443':'K8s API','8080':'HTTP-Alt','8443':'HTTPS-Alt','9000':'PHP-FPM','9090':'Prometheus','9200':'Elasticsearch',
        '11211':'Memcached','27017':'MongoDB','5000':'Flask/Dev','7860':'SD WebUI','8188':'ComfyUI','11434':'Ollama','8000':'AI推理','8001':'AI推理'
    }
    for line in (port_raw.split('\n') if port_raw else []):
        p = line.strip().split('|')
        if len(p) >= 3:
            desc = port_kb.get(p[0], '')
            d['listen_ports'].append({'port': p[0], 'process': p[1], 'scope': p[2], 'desc': desc})

    # 共享文件夹
    shares_raw = ps('Get-SmbShare -EA SilentlyContinue|ForEach-Object{Write-Output \"$($_.Name)|$($_.Path)\"}')
    d['shares'] = []
    for line in (shares_raw.split('\n') if shares_raw else []):
        p = line.strip().split('|')
        if len(p) >= 2:
            d['shares'].append({'name': p[0], 'path': p[1]})

    # 4. 安全配置
    fw = ps('$p=Get-NetFirewallProfile -EA SilentlyContinue;if($p){$p|ForEach-Object{Write-Output \"$($_.Profile)|$($_.Enabled)\"}}')
    d['fw_domain'] = d['fw_private'] = d['fw_public'] = 'N/A'
    for line in (fw.split('\n') if fw else []):
        p = line.strip().split('|')
        if len(p) >= 2:
            if p[0] == 'Domain': d['fw_domain'] = p[1]
            elif p[0] == 'Private': d['fw_private'] = p[1]
            elif p[0] == 'Public': d['fw_public'] = p[1]

    rdp = ps('$e=Get-ItemProperty \"HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server\" -Name fDenyTSConnections -EA SilentlyContinue;if($e.fDenyTSConnections -eq 0){\"已启用\"}else{\"已禁用\"}')
    d['rdp_enabled'] = rdp if rdp else 'N/A'
    d['rdp_port'] = ps('(Get-ItemProperty \"HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp\" -Name PortNumber -EA SilentlyContinue).PortNumber')
    d['rdp_nla'] = ps('$e=Get-ItemProperty \"HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server\\WinStations\\RDP-Tcp\" -Name UserAuthentication -EA SilentlyContinue;if($e.UserAuthentication -eq 1){\"已启用\"}else{\"已禁用\"}')

    bl_raw = ps('$e=Get-BitLockerVolume -EA SilentlyContinue;if($e){$e|ForEach-Object{Write-Output \"$($_.MountPoint)|$($_.ProtectionStatus)\"}}')
    d['bitlocker'] = []
    d['bitlocker_available'] = bool(bl_raw)
    for line in (bl_raw.split('\n') if bl_raw else []):
        p = line.strip().split('|')
        if len(p) >= 2:
            d['bitlocker'].append({'drive': p[0], 'protection': '已保护' if p[1]=='1' else '未保护'})

    def_raw = ps('$e=Get-MpComputerStatus -EA SilentlyContinue;if($e){Write-Output \"$($e.AntivirusEnabled)|$($e.RealTimeProtectionEnabled)|$($e.AMProductVersion)|$($e.AntivirusSignatureVersion)|$($e.AntivirusSignatureLastUpdated)\"}')
    d['defender'] = None
    if def_raw and '|' in def_raw:
        dp = def_raw.split('|')
        if len(dp) >= 5:
            d['defender'] = {'antivirus': dp[0], 'realtime': dp[1], 'prod_ver': dp[2], 'sig_ver': dp[3], 'sig_date': dp[4]}

    pw = ps('$e=net accounts;Write-Output $e')
    d['pw_policy'] = {}
    if pw:
        for line in pw.split('\n'):
            line = line.strip()
            if ':' in line:
                k, v = line.split(':', 1)
                d['pw_policy'][k.strip()] = v.strip()

    updates_raw = ps('Get-HotFix -EA SilentlyContinue|Sort-Object InstalledOn -Descending|Select-Object -First 5|ForEach-Object{Write-Output \"$($_.HotFixID)|$($_.Description)|$($_.InstalledOn.ToString(\"yyyy-MM-dd\"))\"}')
    d['updates'] = []
    for line in (updates_raw.split('\n') if updates_raw else []):
        p = line.strip().split('|')
        if len(p) >= 3:
            d['updates'].append({'id': p[0], 'type': p[1], 'date': p[2]})

    d['audit_available'] = bool(ps('auditpol /get /category:\"\" 2>$null'))
    d['time_status'] = ps('$e=Get-CimInstance Win32_TimeZone;Write-Output $e.Caption')
    d['time_source'] = ps('w32tm /query /source 2>$null')

    # 系统还原点
    rp_raw = ps('Get-ComputerRestorePoint -EA SilentlyContinue|Select-Object -Last 3|ForEach-Object{Write-Output \"$($_.Description)|$($_.CreationTime.ToString(\"yyyy-MM-dd\"))\"}')
    d['restore_points'] = []
    for line in (rp_raw.split('\n') if rp_raw else []):
        p = line.strip().split('|')
        if len(p) >= 2:
            d['restore_points'].append({'desc': p[0], 'date': p[1]})

    # 5. 用户与权限
    users_raw = ps('Get-LocalUser -EA SilentlyContinue|ForEach-Object{Write-Output \"$($_.Name)|$($_.Enabled)|$($_.LastLogon.ToString(\"yyyy-MM-dd\"))\"}')
    d['local_users'] = []
    for line in (users_raw.split('\n') if users_raw else []):
        p = line.strip().split('|')
        if len(p) >= 3:
            d['local_users'].append({'name': p[0], 'enabled': p[1], 'lastlogon': p[2]})

    d['admin_members'] = ps('$g=Get-LocalGroup -Name Administrators -EA SilentlyContinue;if($g){$m=Get-LocalGroupMember -Group $g -EA SilentlyContinue|ForEach-Object{$_.Name};$m -join \", \"}')

    # 6. 进程与服务
    out2 = run_command('tasklist /fo csv /nh')
    procs = []
    if out2['success']:
        for line in out2['stdout'].strip().split('\n'):
            p = line.strip().strip('\"').split('\",\"')
            if len(p) >= 5:
                try:
                    name = p[0]
                    pid = p[1].replace('\"','')
                    mem_kb = int(p[4].replace('\"','').replace(' K','').replace(',',''))
                    procs.append({'name': name, 'pid': pid, 'mem_kb': mem_kb})
                except: pass
    procs.sort(key=lambda x: x['mem_kb'], reverse=True)
    d['proc_count'] = len(procs)
    d['proc_top10'] = procs[:10]

    d['svc_running'] = ps('(Get-Service -EA SilentlyContinue|Where-Object{$_.Status -eq \"Running\"}).Count')

    # 7. 启动项
    startup_raw = ps('Get-CimInstance Win32_StartupCommand -EA SilentlyContinue|ForEach-Object{Write-Output \"$($_.Name)|$($_.Command)\"}')
    d['startup_items'] = []
    for line in (startup_raw.split('\n') if startup_raw else []):
        p = line.strip().split('|')
        if len(p) >= 2:
            d['startup_items'].append({'name': p[0], 'cmd': p[1]})

    # 计划任务
    sched_raw = ps('schtasks /query /fo LIST /v /nh 2>$null')
    d['sched_tasks'] = []
    d['sched_total'] = 0
    if sched_raw:
        current = {}
        for line in sched_raw.split('\n'):
            line = line.strip()
            if ':' in line:
                k, v = line.split(':', 1)
                k, v = k.strip(), v.strip()
                if k == 'TaskName':
                    if current and current.get('name') and 'Microsoft' not in current['name']:
                        d['sched_tasks'].append(current)
                    current = {'name': v}
                elif k == 'Status':
                    current['state'] = v
                elif k == 'Task To Run':
                    current['action'] = v
        if current and current.get('name') and 'Microsoft' not in current['name']:
            d['sched_tasks'].append(current)
        d['sched_total'] = len(d['sched_tasks'])

    # 8. 已安装软件
    sw_raw = ps('Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*,HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* -EA SilentlyContinue|Where-Object{$_.DisplayName}|Select-Object DisplayName,DisplayVersion,Publisher,InstallDate -First 200|ForEach-Object{Write-Output \"$($_.DisplayName)|$($_.DisplayVersion)|$($_.Publisher)|$($_.InstallDate)\"}')
    d['sw_list'] = []
    for line in (sw_raw.split('\n') if sw_raw else []):
        p = line.strip().split('|')
        if len(p) >= 3:
            d['sw_list'].append({'name': p[0], 'ver': p[1], 'pub': p[2], 'date': p[3] if len(p) > 3 else ''})
    d['sw_count'] = len(d['sw_list'])

    # 9. 事件日志
    log_sys = ps('Get-WinEvent -FilterHashtable @{LogName=\"System\";Level=1,2,3} -MaxEvents 200 -EA SilentlyContinue|Group-Object Id,ProviderName|Select-Object Name,Count,@{N=\"First\";E={$_.Group[0].TimeCreated.ToString(\"yyyy-MM-dd HH:mm\")}},@{N=\"Last\";E={$_.Group[-1].TimeCreated.ToString(\"yyyy-MM-dd HH:mm\")}}|ForEach-Object{Write-Output \"$($_.Name)|$($_.Count)|$($_.First)|$($_.Last)\"}')
    d['log_sys_grouped'] = []
    for line in (log_sys.split('\n') if log_sys else []):
        p = line.strip().split('|')
        if len(p) >= 4:
            parts = p[0].split(', ')
            eid = parts[0] if len(parts) > 0 else ''
            src = parts[1] if len(parts) > 1 else ''
            d['log_sys_grouped'].append({'id': eid, 'source': src, 'count': p[1], 'first': p[2], 'last': p[3], 'msg': ''})
    d['log_sys_total'] = sum(int(g['count']) for g in d['log_sys_grouped'])

    log_app = ps('Get-WinEvent -FilterHashtable @{LogName=\"Application\";Level=1,2,3} -MaxEvents 200 -EA SilentlyContinue|Group-Object Id,ProviderName|Select-Object Name,Count,@{N=\"First\";E={$_.Group[0].TimeCreated.ToString(\"yyyy-MM-dd HH:mm\")}},@{N=\"Last\";E={$_.Group[-1].TimeCreated.ToString(\"yyyy-MM-dd HH:mm\")}}|ForEach-Object{Write-Output \"$($_.Name)|$($_.Count)|$($_.First)|$($_.Last)\"}')
    d['log_app_grouped'] = []
    for line in (log_app.split('\n') if log_app else []):
        p = line.strip().split('|')
        if len(p) >= 4:
            parts = p[0].split(', ')
            eid = parts[0] if len(parts) > 0 else ''
            src = parts[1] if len(parts) > 1 else ''
            d['log_app_grouped'].append({'id': eid, 'source': src, 'count': p[1], 'first': p[2], 'last': p[3], 'msg': ''})
    d['log_app_total'] = sum(int(g['count']) for g in d['log_app_grouped'])

    # 10. 电源计划
    d['power_plan'] = ps('powercfg /getactivescheme 2>$null|Select-String -Pattern \"\\(([^)]+)\\)\"|ForEach-Object{$_.Matches.Groups[1].Value}')

    # ===== Docker 与容器 =====
    docker_ver = ps('docker --version 2>$null')
    d['docker'] = {'available': False}
    if docker_ver and 'Docker' in docker_ver:
        d['docker']['available'] = True
        d['docker']['version'] = docker_ver.replace('Docker version ','').strip()
        d['docker']['containers'] = ps('docker ps -a -q 2>$null|Measure-Object -Line|Select-Object -ExpandProperty Lines')
        d['docker']['running'] = ps('docker ps -q 2>$null|Measure-Object -Line|Select-Object -ExpandProperty Lines')
        dps = ps('docker ps --format "{{.ID}}|{{.Image}}|{{.Status}}|{{.Ports}}" 2>$null')
        d['docker_ps'] = []
        for line in (dps.split('\n') if dps else []):
            p = line.strip().split('|')
            if len(p) >= 3:
                d['docker_ps'].append({'id': p[0][:12], 'image': p[1], 'status': p[2], 'ports': p[3] if len(p) > 3 else ''})

    # ===== NPU 加速器 =====
    npu_raw = ps('Get-CimInstance Win32_PnPEntity -EA SilentlyContinue|Where-Object{$_.PNPClass -eq "System" -or $_.Name -like "*NPU*" -or $_.Name -like "*神经*" -or $_.Name -like "*AI*"}|ForEach-Object{Write-Output "$($_.Name)|$($_.Status)"}')
    d['npu'] = []
    for line in (npu_raw.split('\n') if npu_raw else []):
        p = line.strip().split('|')
        if len(p) >= 2:
            name = p[0]
            if any(kw in name.upper() for kw in ['NPU', 'NEURAL', 'AI', '神经', '加速', 'TENSOR', 'GPU', 'CUDA']):
                d['npu'].append({'name': name, 'status': p[1]})
    nvsmi = run_command('nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>&1')
    if nvsmi['success'] and nvsmi['stdout'].strip():
        for line in nvsmi['stdout'].strip().split('\n'):
            if line.strip():
                d['npu'].append({'name': f"GPU (CUDA): {line.strip()}", 'status': 'OK'})

    # ===== AI 推理进程 =====
    ai_kw = ['python','onnx','tensorflow','pytorch','torch','triton','llama','ollama','vllm','tgi','text-generation','transformers','cuda','cudnn','tensorrt','openvino','mediapipe','deepstream']
    out_ai = run_command('tasklist /fo csv /nh')
    d['inference'] = []
    d['inf_ports'] = []
    if out_ai['success']:
        for line in out_ai['stdout'].strip().split('\n'):
            p = line.strip().strip('\"').split('\",\"')
            if len(p) >= 5:
                name = p[0].lower()
                if any(kw in name for kw in ai_kw):
                    try:
                        mem = int(p[4].replace('\"','').replace(' K','').replace(',','')) // 1024
                        d['inference'].append({'name': p[0], 'pid': p[1].replace('\"',''), 'mem_mb': mem})
                    except: pass
    ai_ports = ['8000','8001','8080','5000','5001','7860','8188','9090','11434']
    for port in d.get('listen_ports', []):
        if port['port'] in ai_ports:
            d['inf_ports'].append({'port': port['port'], 'process': port['process']})

    # ===== 电池状态 =====
    bat = ps('$b=Get-CimInstance Win32_Battery -EA SilentlyContinue|Select-Object -First 1;if($b){Write-Output "$($b.EstimatedChargeRemaining)|$($b.BatteryStatus)"}')
    d['battery'] = {}
    if bat and '|' in bat:
        bp = bat.split('|')
        status_map = {'1':'放电中','2':'交流供电','3':'已充满','4':'低电量','5':'临界','6':'充电中','7':'充电中且已满','8':'无电池','9':'未知'}
        d['battery'] = {'charge_pct': bp[0], 'status': status_map.get(bp[1], bp[1])}

    # ===== 温度传感器 =====
    temp_raw = ps('Get-CimInstance -Namespace root/WMI -ClassName MSAcpi_ThermalZoneTemperature -EA SilentlyContinue|ForEach-Object{$k=$_.InstanceName.Split("\\\\")[-1];$t=[math]::Round(($_.CurrentTemperature-2732)/10,1);Write-Output "$k|$t°C"}')
    d['thermal_sensors'] = []
    d['thermal'] = {'cpu_temp': '不可用'}
    if temp_raw:
        for line in temp_raw.split('\n'):
            p = line.strip().split('|')
            if len(p) >= 2:
                d['thermal_sensors'].append({'name': p[0], 'temp': p[1]})
                if 'cpu' in p[0].lower():
                    d['thermal']['cpu_temp'] = p[1]

    # ===== 风扇转速 =====
    fan_raw = ps('Get-CimInstance -Namespace root/CIMV2 -ClassName Win32_Fan -EA SilentlyContinue|ForEach-Object{Write-Output "$($_.Name)|$($_.DesiredSpeed) RPM"}')
    d['fans'] = []
    if fan_raw:
        for line in fan_raw.split('\n'):
            p = line.strip().split('|')
            if len(p) >= 2:
                d['fans'].append({'name': p[0], 'speed': p[1]})

    return d


def generate_html(d: Dict, timestamp: str) -> str:
    def esc(t): return html_mod.escape(str(t))
    try:
        cpu_pct = float(d['cpu_load']) if d['cpu_load'] and d['cpu_load'] != 'N/A' else 0
        mem_pct = d['mem_pct']
        max_disk_pct = max((float(dk['pct'].split('\n')[0].strip()) for dk in d['disks']), default=0)
        today = datetime.datetime.now().strftime('%Y-%m-%d')

        # 日志时间范围
        all_log_times = []
        for g in d.get('log_sys_grouped', []) + d.get('log_app_grouped', []):
            all_log_times.extend([g['first'], g['last']])
        all_log_times = sorted([t for t in all_log_times if t])
        log_range_start = all_log_times[0] if all_log_times else 'N/A'
        log_range_end = all_log_times[-1] if all_log_times else 'N/A'

        # 总体评估
        issues = []
        if cpu_pct > 90: issues.append(('高', 'CPU 使用率过高'))
        if mem_pct > 90: issues.append(('高', '内存使用率过高'))
        if max_disk_pct > 90: issues.append(('高', '磁盘空间不足'))
        if d['license_status'] != '已授权': issues.append(('中', '系统未激活'))
        if d['fw_domain']=='OFF' or d['fw_private']=='OFF' or d['fw_public']=='OFF': issues.append(('高', '防火墙未全部开启'))
        if d['rdp_enabled'] == '已启用': issues.append(('中', '远程桌面已开启'))
        for g in d.get('log_sys_grouped', []):
            if g['id'] == '55' and 'Ntfs' in g['source']: issues.append(('高', f'NTFS 文件系统损坏 ({g["count"]}次)'))
            if g['id'] == '6008': issues.append(('高', f'非正常关机 ({g["count"]}次)'))
            if g['id'] == '41': issues.append(('高', f'意外重启/蓝屏 ({g["count"]}次)'))

        risk_level = '高' if any(i[0]=='高' for i in issues) else '中' if any(i[0]=='中' for i in issues) else '低'

        proc_count = d.get('proc_count', 0)
        svc_running = d.get('svc_running', 'N/A')
        total_issues = len(issues)

        def pct_bar(pct, width=90):
            cls = 'fill-ok' if pct < 70 else 'fill-warn' if pct < 90 else 'fill-crit'
            num_cls = 'green' if pct < 70 else 'orange' if pct < 90 else 'red'
            return f'<span class="progress-bar"><span class="progress-fill {cls}" style="width:{pct}%"></span></span><span class="num {num_cls}">{pct}%</span>'

        # 管理员组成员处理
        admins = d['admin_members']
        if isinstance(admins, str):
            admin_list = admins.split(', ') if admins and admins != 'N/A' else []
        else:
            admin_list = admins

        # 概览卡片数据
        mem_used_gb = f"{d['mem_used']:.1f}"
        mem_total_gb = f"{d['mem_total']:.1f}"
        uptime = esc(d.get('uptime', 'N/A'))

        risk_box_class = 'high' if risk_level == '高' else 'mid' if risk_level == '中' else 'low'
        summary_card_class = 's-crit' if total_issues > 0 else 's-ok'
        summary_num_class = 'red' if total_issues > 0 else 'green'
        user_domain = d.get('user', '').split('\\')[0] if '\\' in d.get('user', '') else 'N/A'

        h = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Windows 系统巡检报告 - {esc(d['hostname'])}</title>
<style>
  :root {{
    --c-primary: #1976d2;
    --c-primary-2: #1565c0;
    --c-primary-dark: #0d47a1;
    --c-primary-soft: #e8f1fc;
    --c-primary-soft-2: #f0f6ff;
    --c-text: #1f2937;
    --c-text-2: #4b5563;
    --c-muted: #6b7280;
    --c-bg: #f3f5f9;
    --c-card: #ffffff;
    --c-border: #d9dee7;
    --c-border-light: #eaedf3;
    --c-stripe: #fafbfd;
    --c-ok: #16a34a;
    --c-ok-soft: #e9f8ee;
    --c-warn: #d97706;
    --c-warn-soft: #fff4e0;
    --c-crit: #dc2626;
    --c-crit-soft: #fde8e8;
    --c-info: #1976d2;
    --c-info-soft: #e8f1fc;
    --c-side-bg: #0f172a;
    --c-side-text: #cbd5e1;
    --c-side-muted: #64748b;
    --c-side-active: rgba(25,118,210,0.18);
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 10px;
    --shadow-sm: 0 1px 2px rgba(15,23,42,0.05);
    --shadow-md: 0 2px 8px rgba(15,23,42,0.06), 0 1px 3px rgba(15,23,42,0.05);
    --shadow-lg: 0 8px 24px rgba(15,23,42,0.10);
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
    --font-mono: ui-monospace, "SFMono-Regular", "Cascadia Code", "JetBrains Mono", Consolas, "Liberation Mono", "Menlo", "Courier New", monospace;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{ font-family: var(--font-sans); font-size: 14px; background: var(--c-bg); color: var(--c-text); line-height: 1.55; -webkit-font-smoothing: antialiased; }}
  .toc {{ position: fixed; left: 0; top: 0; bottom: 0; width: 220px; background: var(--c-side-bg); padding: 22px 0 16px; overflow-y: auto; z-index: 10; }}
  .toc-brand {{ padding: 0 22px 16px; border-bottom: 1px solid rgba(255,255,255,0.08); margin-bottom: 12px; display: flex; align-items: center; gap: 10px; }}
  .toc-brand .logo {{ width: 28px; height: 28px; background: var(--c-primary); border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
  .toc-brand .logo svg {{ width: 16px; height: 16px; fill: #fff; }}
  .toc-brand .meta .name {{ font-size: 13px; font-weight: 600; color: #fff; letter-spacing: 0.2px; }}
  .toc-brand .meta .ver {{ font-size: 11px; color: var(--c-side-muted); font-family: var(--font-mono); margin-top: 1px; }}
  .toc a {{ display: flex; align-items: center; gap: 10px; padding: 9px 22px; color: var(--c-side-text); font-size: 13px; text-decoration: none; border-left: 3px solid transparent; transition: background 0.12s, color 0.12s, border-color 0.12s; }}
  .toc a:hover {{ background: rgba(255,255,255,0.05); color: #fff; }}
  .toc a.active {{ background: var(--c-side-active); border-left-color: var(--c-primary); color: #fff; font-weight: 500; }}
  .toc a svg {{ width: 14px; height: 14px; flex-shrink: 0; opacity: 0.7; }}
  .toc a.active svg {{ opacity: 1; }}
  .container {{ max-width: 1280px; margin: 24px auto 24px 240px; padding: 0 28px; }}
  .header {{ background: linear-gradient(135deg, var(--c-primary) 0%, var(--c-primary-dark) 100%); color: #fff; padding: 22px 28px 18px; border-radius: var(--radius-lg); margin-bottom: 18px; box-shadow: var(--shadow-md); position: relative; overflow: hidden; }}
  .header::after {{ content: ""; position: absolute; right: -40px; top: -40px; width: 240px; height: 240px; background: radial-gradient(circle, rgba(255,255,255,0.10) 0%, transparent 70%); pointer-events: none; }}
  .header-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; position: relative; z-index: 1; }}
  .header h1 {{ font-size: 20px; font-weight: 700; letter-spacing: -0.2px; }}
  .header h1 .tag {{ display: inline-block; background: rgba(255,255,255,0.20); color: #fff; font-size: 11px; padding: 3px 9px; border-radius: var(--radius-sm); margin-right: 8px; vertical-align: middle; font-weight: 600; }}
  .header-action {{ display: inline-flex; align-items: center; gap: 6px; background: rgba(255,255,255,0.15); color: #fff; padding: 7px 14px; border-radius: var(--radius-sm); font-size: 12px; border: 1px solid rgba(255,255,255,0.25); cursor: default; }}
  .header-action svg {{ width: 13px; height: 13px; fill: currentColor; }}
  .header-meta {{ display: flex; flex-wrap: wrap; gap: 22px 32px; position: relative; z-index: 1; }}
  .header-meta .field {{ font-size: 12.5px; }}
  .header-meta .field .k {{ color: rgba(255,255,255,0.7); margin-right: 6px; }}
  .header-meta .field .v {{ color: #fff; font-weight: 500; font-family: var(--font-mono); }}
  .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px; }}
  .summary-card {{ background: var(--c-card); border-radius: var(--radius-md); padding: 14px; box-shadow: var(--shadow-sm); border: 1px solid var(--c-border-light); display: flex; align-items: center; gap: 12px; }}
  .summary-card .ico {{ width: 38px; height: 38px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
  .summary-card .ico svg {{ width: 18px; height: 18px; fill: #fff; }}
  .summary-card.s-ok .ico {{ background: var(--c-ok); }}
  .summary-card.s-warn .ico {{ background: var(--c-warn); }}
  .summary-card.s-crit .ico {{ background: var(--c-crit); }}
  .summary-card.s-info .ico {{ background: var(--c-primary); }}
  .summary-card.s-purple .ico {{ background: #8b5cf6; }}
  .summary-card .body {{ flex: 1; min-width: 0; }}
  .summary-card .num {{ font-family: var(--font-sans); font-size: 22px; font-weight: 700; line-height: 1.1; letter-spacing: -0.5px; }}
  .summary-card .label {{ font-size: 11px; color: var(--c-muted); margin-top: 4px; line-height: 1.3; }}
  .num.green {{ color: var(--c-ok); }}
  .num.orange {{ color: var(--c-warn); }}
  .num.red {{ color: var(--c-crit); }}
  .section {{ background: var(--c-card); border-radius: var(--radius-lg); margin-bottom: 14px; box-shadow: var(--shadow-sm); border: 1px solid var(--c-border-light); overflow: hidden; }}
  .section[id] {{ scroll-margin-top: 16px; }}
  .section > *:not(h2) {{ padding-left: 24px; padding-right: 24px; }}
  .section > h2 {{ font-size: 15px; font-weight: 700; color: var(--c-primary-dark); margin: 0; padding: 12px 22px; background: var(--c-primary-soft-2); border-bottom: 1px solid var(--c-border-light); display: flex; align-items: center; }}
  .section > h2 .num {{ display: inline-block; color: var(--c-primary); font-weight: 700; margin-right: 8px; min-width: 18px; }}
  .section > *:first-child + * {{ padding-top: 18px; }}
  .section > *:last-child {{ padding-bottom: 20px; }}
  .section h3 {{ font-size: 12.5px; font-weight: 600; color: var(--c-text-2); margin: 18px 0 10px; }}
  .section h3:first-of-type {{ margin-top: 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 4px; }}
  th {{ background: var(--c-primary-soft-2); text-align: left; padding: 10px 12px; font-weight: 600; font-size: 12px; color: var(--c-text-2); border-bottom: 1px solid var(--c-border-light); white-space: nowrap; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid var(--c-border-light); word-break: break-all; vertical-align: top; font-size: 12.5px; line-height: 1.5; color: var(--c-text); }}
  tr:nth-child(even) td {{ background: var(--c-stripe); }}
  tr:hover td {{ background: var(--c-primary-soft); }}
  tr:last-child td {{ border-bottom: none; }}
  td.text {{ font-family: var(--font-sans); font-size: 13px; }}
  .badge {{ display: inline-block; padding: 2px 9px; border-radius: 10px; font-size: 11.5px; font-weight: 600; line-height: 1.5; font-family: var(--font-sans); }}
  .badge.ok {{ background: var(--c-ok-soft); color: var(--c-ok); }}
  .badge.warning {{ background: var(--c-warn-soft); color: var(--c-warn); }}
  .badge.critical {{ background: var(--c-crit-soft); color: var(--c-crit); }}
  .badge.info {{ background: var(--c-info-soft); color: var(--c-info); }}
  .info-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px 28px; }}
  .info-item {{ padding: 10px 0; border-bottom: 1px dashed var(--c-border-light); }}
  .info-item:nth-last-child(-n+4) {{ border-bottom: none; }}
  .info-item .key {{ color: var(--c-muted); font-size: 11.5px; display: block; margin-bottom: 3px; font-weight: 500; }}
  .info-item .val {{ color: var(--c-text); font-size: 13px; word-break: break-all; font-weight: 500; }}
  .progress-bar {{ background: var(--c-border-light); border-radius: var(--radius-sm); height: 6px; overflow: hidden; display: inline-block; width: 90px; vertical-align: middle; margin-right: 8px; }}
  .progress-fill {{ height: 100%; transition: width 0.3s; }}
  .fill-ok {{ background: var(--c-ok); }}
  .fill-warn {{ background: var(--c-warn); }}
  .fill-crit {{ background: var(--c-crit); }}
  .risk-box {{ display: inline-block; padding: 2px 14px; border-radius: var(--radius-sm); font-size: 14px; font-weight: 700; }}
  .risk-box.high {{ background: var(--c-crit-soft); color: var(--c-crit); }}
  .risk-box.mid {{ background: var(--c-warn-soft); color: var(--c-warn); }}
  .risk-box.low {{ background: var(--c-ok-soft); color: var(--c-ok); }}
  .issue-list {{ list-style: none; padding: 0; margin: 8px 0; }}
  .issue-item {{ display: flex; align-items: flex-start; gap: 10px; padding: 10px 14px; border-radius: var(--radius-sm); margin-bottom: 6px; border: 1px solid var(--c-border-light); }}
  .issue-item .level {{ flex-shrink: 0; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: var(--radius-sm); }}
  .issue-item .level.high {{ background: var(--c-crit-soft); color: var(--c-crit); }}
  .issue-item .level.mid {{ background: var(--c-warn-soft); color: var(--c-warn); }}
  .issue-item .level.low {{ background: var(--c-ok-soft); color: var(--c-ok); }}
  .issue-item .desc {{ flex: 1; font-size: 13px; color: var(--c-text); }}
  pre {{ background: #0f172a; color: #cbd5e1; border: 1px solid #1e293b; padding: 14px 16px; border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: 12px; line-height: 1.6; overflow-x: auto; white-space: pre-wrap; word-break: break-all; max-height: 340px; overflow-y: auto; margin-bottom: 4px; }}
  .footer {{ text-align: center; color: var(--c-muted); font-size: 12px; padding: 22px 0 12px; }}
  .footer .sep {{ color: var(--c-border); margin: 0 8px; }}
  @media (max-width: 900px) {{
    .toc {{ position: relative; width: 100%; height: auto; padding: 14px 16px; }}
    .toc a {{ display: inline-flex; padding: 4px 10px; border-left: none; border-radius: var(--radius-sm); margin: 2px; font-size: 12px; }}
    .container {{ margin-left: auto; margin-right: auto; padding: 16px; }}
    .summary {{ grid-template-columns: repeat(2, 1fr); }}
    .info-grid {{ grid-template-columns: 1fr; }}
    .header-action {{ display: none; }}
  }}
  @media print {{
    body {{ background: #fff; font-size: 10.5pt; color: #000; }}
    .toc, .footer, .header-action {{ display: none !important; }}
    .container {{ margin: 0; max-width: 100%; padding: 0; }}
    .header {{ background: var(--c-primary-2) !important; color: #fff !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .section, .summary-card {{ box-shadow: none; border: 1px solid #ccc; page-break-inside: avoid; }}
    table {{ page-break-inside: auto; }}
    tr {{ page-break-inside: avoid; }}
  }}
</style>
</head>
<body>
<nav class="toc">
  <div class="toc-brand">
    <div class="logo"><svg viewBox="0 0 24 24"><path d="M4 4h16v2H4zm0 5h16v2H4zm0 5h16v2H4zm0 5h16v2H4z"/></svg></div>
    <div class="meta">
      <div class="name">Windows Inspection</div>
      <div class="ver">v2.0</div>
    </div>
  </div>
  <a href="#sec-summary">概览</a>
  <a href="#sec-s1">一、主机基本信息</a>
  <a href="#sec-s2">二、硬件资源状态</a>
  <a href="#sec-s3">三、网络配置与连接</a>
  <a href="#sec-s4">四、安全配置审计</a>
  <a href="#sec-s5">五、用户与权限</a>
  <a href="#sec-s6">六、进程与服务</a>
  <a href="#sec-s7">七、启动项与计划任务</a>
  <a href="#sec-s8">八、已安装软件</a>
  <a href="#sec-s9">九、事件日志分析</a>
  <a href="#sec-s10">十、Docker 与容器</a>
  <a href="#sec-s11">十一、NPU 与 AI 推理</a>
  <a href="#sec-s12">十二、电源与散热</a>
  <a href="#sec-s13">十三、风险评估与建议</a>
</nav>
<div class="container">
<div class="header">
  <div class="header-top">
    <h1><span class="tag">Windows</span>系统巡检报告</h1>
    <div class="header-action"><svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>巡检完成</div>
  </div>
  <div class="header-meta">
    <div class="field"><span class="k">主机名</span><span class="v">{esc(d['hostname'])}</span></div>
    <div class="field"><span class="k">操作系统</span><span class="v">{esc(d['os'])}</span></div>
    <div class="field"><span class="k">运行时间</span><span class="v">{uptime}</span></div>
    <div class="field"><span class="k">巡检日期</span><span class="v">{today}</span></div>
    <div class="field"><span class="k">巡检人员</span><span class="v">{esc(d['user'])}</span></div>
    <div class="field"><span class="k">综合风险</span><span class="v"><span class="risk-box {risk_box_class}">{esc(risk_level)}</span></span></div>
  </div>
</div>
<div class="summary" id="sec-summary">
  <div class="summary-card s-info">
    <div class="ico"><svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg></div>
    <div class="body"><div class="num">{esc(d['cpu_threads'])}</div><div class="label">CPU 线程 / {esc(d['cpu_cores'])} 核心</div></div>
  </div>
  <div class="summary-card s-ok">
    <div class="ico"><svg viewBox="0 0 24 24"><path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"/></svg></div>
    <div class="body"><div class="num">{mem_used_gb} / {mem_total_gb} GB</div><div class="label">内存使用 {pct_bar(mem_pct)}</div></div>
  </div>
  <div class="summary-card s-purple">
    <div class="ico"><svg viewBox="0 0 24 24"><path d="M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z"/></svg></div>
    <div class="body"><div class="num">{proc_count}</div><div class="label">进程数 / {esc(svc_running)} 服务运行中</div></div>
  </div>
  <div class="summary-card {summary_card_class}">
    <div class="ico"><svg viewBox="0 0 24 24"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg></div>
    <div class="body"><div class="num {summary_num_class}">{total_issues}</div><div class="label">发现问题 · 风险 {esc(risk_level)}</div></div>
  </div>
</div>
<div class="section" id="sec-s1">
  <h2><span class="num">一</span>目标主机基本信息</h2>
  <div class="info-grid">
    <div class="info-item"><span class="key">计算机名</span><span class="val">{esc(d['hostname'])}</span></div>
    <div class="info-item"><span class="key">操作系统</span><span class="val">{esc(d['os'])}</span></div>
    <div class="info-item"><span class="key">架构</span><span class="val">{esc(d['arch'])}</span></div>
    <div class="info-item"><span class="key">域/工作组</span><span class="val">{esc(user_domain)}</span></div>
    <div class="info-item"><span class="key">主板</span><span class="val">{esc(d['motherboard'])}</span></div>
    <div class="info-item"><span class="key">BIOS</span><span class="val">{esc(d['bios'])}</span></div>
    <div class="info-item"><span class="key">许可证</span><span class="val">{esc(d['license_status'])} ({esc(d['license_type'])})</span></div>
    <div class="info-item"><span class="key">运行时间</span><span class="val">{uptime}</span></div>
    <div class="info-item"><span class="key">安全启动</span><span class="val">{esc(d['secure_boot'])}</span></div>
    <div class="info-item"><span class="key">电源计划</span><span class="val">{esc(d['power_plan'])}</span></div>
  </div>
</div>
<div class="section" id="sec-s2">
  <h2><span class="num">二</span>硬件资源状态</h2>
  <h3>CPU</h3>
  <table><tr><th>型号</th><th>核心数</th><th>线程数</th><th>频率</th><th>使用率</th></tr>
    <tr><td class="text">{esc(d['cpu_name'])}</td><td>{esc(d['cpu_cores'])}</td><td>{esc(d['cpu_threads'])}</td><td>{esc(d['cpu_freq'])} MHz</td><td>{esc(d['cpu_load'])}%</td></tr>
  </table>
  <h3>内存</h3>
  <table><tr><th>总计</th><th>已用</th><th>空闲</th><th>使用率</th></tr>
    <tr><td>{d['mem_total']:.2f} GB</td><td>{d['mem_used']:.2f} GB</td><td>{d['mem_free']:.2f} GB</td>
    <td>{pct_bar(mem_pct)}</td></tr>
  </table>
  <h3>内存条信息</h3>
  <table><tr><th>制造商</th><th>容量</th><th>频率</th><th>型号</th></tr>
"""

        for chip in d['mem_chips']:
            p = chip.split('|')
            if len(p) >= 4:
                h += f'    <tr><td>{esc(p[0])}</td><td>{esc(p[1])}</td><td>{esc(p[2])}</td><td>{esc(p[3])}</td></tr>\n'

        h += f"""  </table>
  <h3>磁盘存储</h3>
  <table><tr><th>盘符</th><th>卷标</th><th>总容量</th><th>已用</th><th>可用</th><th>使用率</th></tr>
"""

        for dk in d['disks']:
            pct = float(dk['pct'])
            h += f'    <tr><td><b>{esc(dk["drive"])}</b></td><td>{esc(dk["label"])}</td><td>{esc(dk["total"])} GB</td><td>{esc(dk["used"])} GB</td><td>{esc(dk["free"])} GB</td><td>{pct_bar(pct)}</td></tr>\n'

        h += f"""  </table>
  <h3>物理磁盘健康</h3>
  <table><tr><th>磁盘</th><th>类型</th><th>大小</th><th>总线</th><th>状态</th></tr>
"""

        for pd in d['physical_disks']:
            hc = 'ok' if pd['health']=='Healthy' else 'critical'
            hl = '健康' if pd['health']=='Healthy' else pd['health']
            h += f'    <tr><td>{esc(pd["name"])}</td><td>{esc(pd["type"])}</td><td>{esc(pd["size"])}</td><td>{esc(pd["bus"])}</td><td><span class="badge {hc}">{esc(hl)}</span></td></tr>\n'

        h += f"""  </table>
  <h3>GPU / 驱动</h3>
  <table><tr><th>GPU</th><th>驱动版本</th></tr>
    <tr><td class="text">{esc(d['gpu'])}</td><td>{esc(d['gpu_driver'])}</td></tr>
  </table>
</div>
<div class="section" id="sec-s3">
  <h2><span class="num">三</span>网络配置与连接</h2>
  <h3>网络适配器</h3>
  <table><tr><th>名称</th><th>状态</th><th>速率</th><th>MAC 地址</th></tr>
"""

        for a in d['net_adapters']:
            st = '<span class="badge ok">Up</span>' if a['status']=='Up' else f'<span class="badge info">{esc(a["status"])}</span>'
            h += f'    <tr><td class="text">{esc(a["name"])}</td><td>{st}</td><td>{esc(a["speed"])}</td><td>{esc(a["mac"])}</td></tr>\n'

        h += f"""  </table>
  <h3>IP 地址分配</h3>
  <table><tr><th>适配器</th><th>IPv4 地址</th><th>子网</th><th>来源</th></tr>
"""

        origin_map = {'Manual':'手动','Dhcp':'DHCP','WellKnown':'自动','RouterAdvertisement':'路由通告'}
        for a in d['ipv4_addrs']:
            h += f'    <tr><td class="text">{esc(a["iface"])}</td><td><b>{esc(a["ip"])}</b></td><td>/{esc(a["prefix"])}</td><td>{esc(origin_map.get(a["origin"],a["origin"]))}</td></tr>\n'

        h += f"""  </table>
  <div class="info-grid">
    <div class="info-item"><span class="key">默认网关</span><span class="val">{esc(d['gateway'])}</span></div>
    <div class="info-item"><span class="key">DNS 服务器</span><span class="val">{esc(d['dns'])}</span></div>
    <div class="info-item"><span class="key">网络流量</span><span class="val">接收 {d['net_rx']} / 发送 {d['net_tx']}</span></div>
    <div class="info-item"><span class="key">连接统计</span><span class="val">已建立 {d['conn_established']} | 监听 {d['conn_listening']} | TIME_WAIT {d['conn_timewait']}</span></div>
  </div>
  <h3>监听端口</h3>
  <table><tr><th>端口</th><th>进程</th><th>监听范围</th><th>说明</th></tr>
"""

        for p in d['listen_ports'][:30]:
            h += f'    <tr><td><b>{esc(p["port"])}</b></td><td class="text">{esc(p["process"])}</td><td>{esc(p["scope"])}</td><td style="color:var(--c-muted)">{esc(p["desc"])}</td></tr>\n'
        if len(d['listen_ports']) > 30:
            h += f'    <tr><td colspan="4" style="color:var(--c-muted)">... 共 {len(d["listen_ports"])} 个端口</td></tr>\n'

        h += f"""  </table>
  <h3>共享文件夹</h3>
  <table><tr><th>共享名</th><th>路径</th></tr>
"""

        for s in d['shares']:
            h += f'    <tr><td>{esc(s["name"])}</td><td class="text">{esc(s["path"])}</td></tr>\n'

        h += f"""  </table>
</div>
<div class="section" id="sec-s4">
  <h2><span class="num">四</span>安全配置审计</h2>
  <div class="info-grid">
    <div class="info-item"><span class="key">防火墙(域)</span><span class="val">{esc(d['fw_domain'])}</span></div>
    <div class="info-item"><span class="key">防火墙(专用)</span><span class="val">{esc(d['fw_private'])}</span></div>
    <div class="info-item"><span class="key">防火墙(公用)</span><span class="val">{esc(d['fw_public'])}</span></div>
    <div class="info-item"><span class="key">RDP 端口</span><span class="val">{esc(d['rdp_port'])}</span></div>
    <div class="info-item"><span class="key">RDP 启用</span><span class="val">{esc(d['rdp_enabled'])}</span></div>
    <div class="info-item"><span class="key">RDP NLA</span><span class="val">{esc(d['rdp_nla'])}</span></div>
    <div class="info-item"><span class="key">BitLocker</span><span class="val">{'、'.join(f'{b["drive"]} {b["protection"]}' for b in d['bitlocker']) if d['bitlocker_available'] else '未启用/不可用'}</span></div>
"""

        if d.get('defender'):
            dd = d['defender']
            h += f"""    <div class="info-item"><span class="key">Defender 防病毒</span><span class="val">{esc(dd['antivirus'])} | 实时: {esc(dd['realtime'])}</span></div>
    <div class="info-item"><span class="key">病毒库版本</span><span class="val">{esc(dd['sig_ver'])} ({esc(dd['sig_date'])})</span></div>
"""

        h += f"""    <div class="info-item"><span class="key">审计策略</span><span class="val">{"已配置" if d["audit_available"] else "需要管理员权限"}</span></div>
    <div class="info-item"><span class="key">时间同步</span><span class="val">{esc(d['time_status'])}</span></div>
    <div class="info-item"><span class="key">时间源</span><span class="val">{esc(d['time_source'])}</span></div>
  </div>
  <h3>密码策略</h3>
  <table><tr><th>策略项</th><th>值</th></tr>
"""

        for k, v in d['pw_policy'].items():
            h += f'    <tr><td class="text">{esc(k)}</td><td>{esc(v)}</td></tr>\n'

        h += f"""  </table>
  <h3>系统更新</h3>
  <table><tr><th>补丁号</th><th>类型</th><th>安装日期</th></tr>
"""

        for u in d['updates']:
            h += f'    <tr><td><b>{esc(u["id"])}</b></td><td>{esc(u["type"])}</td><td>{esc(u["date"])}</td></tr>\n'

        h += f"""  </table>
</div>
<div class="section" id="sec-s5">
  <h2><span class="num">五</span>用户与权限</h2>
  <h3>本地用户</h3>
  <table><tr><th>用户名</th><th>启用</th><th>最后登录</th></tr>
"""

        for u in d['local_users']:
            en = '<span class="badge ok">是</span>' if u['enabled']=='True' else '<span class="badge info">否</span>'
            h += f'    <tr><td>{esc(u["name"])}</td><td>{en}</td><td>{esc(u["lastlogon"])}</td></tr>\n'

        h += f"""  </table>
  <h3>管理员组成员</h3>
  <table><tr><th>成员</th></tr>
"""

        for m in admin_list:
            h += f'    <tr><td class="text">{esc(m)}</td></tr>\n'

        h += f"""  </table>
</div>
<div class="section" id="sec-s6">
  <h2><span class="num">六</span>进程与服务分析</h2>
  <div class="info-grid">
    <div class="info-item"><span class="key">进程总数</span><span class="val">{proc_count}</span></div>
    <div class="info-item"><span class="key">运行中服务</span><span class="val">{esc(svc_running)}</span></div>
  </div>
  <h3>内存占用 Top 10</h3>
  <table><tr><th>#</th><th>进程名</th><th>PID</th><th>内存 (MB)</th></tr>
"""

        for i, p in enumerate(d['proc_top10'], 1):
            h += f'    <tr><td>{i}</td><td class="text">{esc(p["name"])}</td><td>{p["pid"]}</td><td>{p["mem_kb"]//1024}</td></tr>\n'

        h += f"""  </table>
</div>
<div class="section" id="sec-s7">
  <h2><span class="num">七</span>启动项与计划任务</h2>
  <h3>启动项</h3>
  <table><tr><th>名称</th><th>命令</th></tr>
"""

        for s in d['startup_items']:
            cmd = s['cmd'] if len(s['cmd'])<=90 else s['cmd'][:87]+'...'
            h += f'    <tr><td class="text">{esc(s["name"])}</td><td class="text" style="font-family:var(--font-mono);font-size:12px">{esc(cmd)}</td></tr>\n'

        h += f"""  </table>
  <h3>非微软计划任务（共 {esc(d.get("sched_total","N/A"))} 个）</h3>
  <table><tr><th>任务名称</th><th>状态</th><th>操作</th></tr>
"""

        for t in d['sched_tasks']:
            st = f'<span class="badge ok">{esc(t["state"])}</span>' if t['state']=='Running' else f'<span class="badge info">{esc(t["state"])}</span>'
            act = t['action'] if len(t['action'])<=70 else t['action'][:67]+'...'
            h += f'    <tr><td class="text">{esc(t["name"])}</td><td>{st}</td><td class="text" style="font-size:12px">{esc(act)}</td></tr>\n'

        h += f"""  </table>
</div>
<div class="section" id="sec-s8">
  <h2><span class="num">八</span>已安装软件</h2>
  <p style="font-size:12.5px;color:var(--c-muted);margin-bottom:4px">共 {d["sw_count"]} 款软件</p>
  <table><tr><th>软件名称</th><th>版本</th><th>发布者</th><th>安装日期</th></tr>
"""

        for s in d['sw_list'][:25]:
            h += f'    <tr><td class="text">{esc(s["name"])}</td><td>{esc(s["ver"])}</td><td class="text">{esc(s["pub"])}</td><td>{esc(s.get("date",""))}</td></tr>\n'
        if d['sw_count'] > 25:
            h += f'    <tr><td colspan="4" style="color:var(--c-muted)">... 共 {d["sw_count"]} 个，仅显示前 25 个</td></tr>\n'

        h += f"""  </table>
</div>
<div class="section" id="sec-s9">
  <h2><span class="num">九</span>事件日志分析</h2>
  <div class="info-grid">
    <div class="info-item"><span class="key">系统日志事件</span><span class="val">{d.get('log_sys_total', 0)}</span></div>
    <div class="info-item"><span class="key">应用日志事件</span><span class="val">{d.get('log_app_total', 0)}</span></div>
  </div>
  <h3>系统日志聚合</h3>
  <table><tr><th>事件 ID</th><th>级别</th><th>来源</th><th>描述</th><th>次数</th></tr>
"""

        for g in d.get('log_sys_grouped', []):
            h += f'    <tr><td>{esc(g["id"])}</td><td><span class="badge info">{esc(g["source"])}</span></td><td class="text">{esc(g["source"])}</td><td class="text">{esc(g["msg"])}</td><td>{g["count"]}</td></tr>\n'

        h += f"""  </table>
  <h3>应用日志聚合</h3>
  <table><tr><th>事件 ID</th><th>级别</th><th>来源</th><th>描述</th><th>次数</th></tr>
"""

        for g in d.get('log_app_grouped', []):
            h += f'    <tr><td>{esc(g["id"])}</td><td><span class="badge info">{esc(g["source"])}</span></td><td class="text">{esc(g["source"])}</td><td class="text">{esc(g["msg"])}</td><td>{g["count"]}</td></tr>\n'

        h += f"""  </table>
</div>
<div class="section" id="sec-s10">
  <h2><span class="num">十</span>Docker 与容器</h2>
"""

        docker = d.get('docker', {'available': False})
        if docker.get('available'):
            h += f"""  <div class="info-grid">
    <div class="info-item"><span class="key">Docker 版本</span><span class="val">{esc(docker.get('version', ''))}</span></div>
    <div class="info-item"><span class="key">容器总数</span><span class="val">{esc(docker.get('containers', '0'))}</span></div>
    <div class="info-item"><span class="key">运行中</span><span class="val">{esc(docker.get('running', '0'))}</span></div>
  </div>
"""
            docker_ps = d.get('docker_ps', [])
            if docker_ps:
                h += f"""  <h3>运行中的容器</h3>
  <table><tr><th>容器 ID</th><th>镜像</th><th>状态</th><th>端口映射</th></tr>
"""
                for c in docker_ps:
                    h += f'    <tr><td style="font-family:var(--font-mono);font-size:12px">{esc(c["id"])}</td><td class="text">{esc(c["image"])}</td><td>{esc(c["status"])}</td><td>{esc(c.get("ports",""))}</td></tr>\n'
                h += '  </table>\n'
        else:
            h += '  <p style="font-size:13px;color:var(--c-muted);padding:8px 0">Docker 未安装或未运行</p>\n'

        h += f"""</div>
<div class="section" id="sec-s11">
  <h2><span class="num">十一</span>NPU 与 AI 推理</h2>
  <h3>NPU 加速器</h3>
"""

        npu_list = d.get('npu', [])
        if npu_list:
            h += f"""  <table><tr><th>名称</th><th>状态</th></tr>
"""
            for n in npu_list:
                st = '<span class="badge ok">正常</span>' if n['status']=='OK' else f'<span class="badge info">{esc(n["status"])}</span>'
                h += f'    <tr><td class="text">{esc(n["name"])}</td><td>{st}</td></tr>\n'
            h += '  </table>\n'
        else:
            h += '  <p style="font-size:13px;color:var(--c-muted);padding:8px 0">未检测到 NPU 设备</p>\n'

        h += f"""  <h3>AI 推理进程</h3>
"""

        inference = d.get('inference', [])
        if inference:
            h += f"""  <table><tr><th>进程名</th><th>PID</th><th>内存 (MB)</th></tr>
"""
            for inf in inference:
                h += f'    <tr><td class="text">{esc(inf["name"])}</td><td>{esc(inf["pid"])}</td><td>{esc(inf["mem_mb"])}</td></tr>\n'
            h += '  </table>\n'
        else:
            h += '  <p style="font-size:13px;color:var(--c-muted);padding:8px 0">未检测到 AI 推理进程</p>\n'

        inf_ports = d.get('inf_ports', [])
        if inf_ports:
            h += f"""  <h3>推理服务端口</h3>
  <table><tr><th>端口</th><th>进程</th></tr>
"""
            for ip in inf_ports:
                h += f'    <tr><td><b>{esc(ip["port"])}</b></td><td class="text">{esc(ip["process"])}</td></tr>\n'
            h += '  </table>\n'

        h += f"""</div>
<div class="section" id="sec-s12">
  <h2><span class="num">十二</span>电源与散热</h2>
"""

        battery = d.get('battery', {})
        if battery and battery.get('charge_pct', 'N/A') != 'N/A':
            h += f"""  <h3>电池状态</h3>
  <div class="info-grid">
    <div class="info-item"><span class="key">剩余电量</span><span class="val">{esc(battery.get('charge_pct', 'N/A'))}%</span></div>
    <div class="info-item"><span class="key">状态</span><span class="val">{esc(battery.get('status', 'N/A'))}</span></div>
  </div>
"""

        thermal = d.get('thermal', {})
        thermal_sensors = d.get('thermal_sensors', [])
        if thermal.get('cpu_temp') and '不可用' not in thermal['cpu_temp']:
            h += f"""  <h3>温度</h3>
  <div class="info-grid">
    <div class="info-item"><span class="key">CPU 温度</span><span class="val">{esc(thermal['cpu_temp'])}</span></div>
  </div>
"""
        elif thermal_sensors:
            h += f"""  <h3>温度传感器</h3>
  <table><tr><th>传感器</th><th>温度</th></tr>
"""
            for ts in thermal_sensors:
                h += f'    <tr><td class="text">{esc(ts["name"])}</td><td>{esc(ts["temp"])}</td></tr>\n'
            h += '  </table>\n'
        else:
            h += '  <p style="font-size:13px;color:var(--c-muted);padding:8px 0">温度数据不可用（需管理员权限或 OpenHardwareMonitor）</p>\n'

        fans = d.get('fans', [])
        if fans:
            h += f"""  <h3>风扇转速</h3>
  <table><tr><th>风扇</th><th>转速</th></tr>
"""
            for fan in fans:
                h += f'    <tr><td class="text">{esc(fan["name"])}</td><td>{esc(fan["speed"])}</td></tr>\n'
            h += '  </table>\n'

        h += f"""  <h3>电源计划</h3>
  <p style="font-size:13px;padding:8px 0">{esc(d['power_plan'])}</p>
</div>
<div class="section" id="sec-s13">
  <h2><span class="num">十三</span>风险评估与建议</h2>
  <p style="margin-bottom:10px">综合风险等级：<span class="risk-box {risk_box_class}" style="font-size:16px;padding:4px 18px">{esc(risk_level)}</span></p>
"""

        if issues:
            h += f"""  <h3>发现的问题</h3>
  <div class="issue-list">
"""
            for lv, desc in issues:
                lv_cls = 'high' if lv=='高' else 'mid' if lv=='中' else 'low'
                h += f'    <div class="issue-item"><span class="level {lv_cls}">{esc(lv)}</span><span class="desc">{esc(desc)}</span></div>\n'
            h += '  </div>\n'

        h += f"""</div>
<div class="footer">巡检日期: {today} &nbsp;<span class="sep">|</span>&nbsp; 主机: {esc(d['hostname'])} &nbsp;<span class="sep">|</span>&nbsp; 生成时间: {timestamp}</div>
</div>
<script>
// 侧边栏滚动高亮
(function() {{
  var links = document.querySelectorAll('.toc a');
  var sections = [];
  links.forEach(function(a) {{
    var id = a.getAttribute('href').substring(1);
    var el = document.getElementById(id);
    if (el) sections.push({{el: el, link: a}});
  }});
  function onScroll() {{
    var scrollY = window.scrollY + 100;
    var active = null;
    sections.forEach(function(s) {{
      if (s.el.offsetTop <= scrollY) active = s;
    }});
    sections.forEach(function(s) {{
      s.link.classList.toggle('active', s === active);
    }});
  }}
  window.addEventListener('scroll', onScroll, {{passive: true}});
  onScroll();
}})();
</script>
</body>
</html>"""
        return h
    except Exception as e:
        return f"<html><body><h1>报告生成失败</h1><pre>{html_mod.escape(str(e))}</pre></body></html>"



def generate_json(d: Dict, timestamp: str) -> str:
    """生成 JSON 报告"""
    report = {
        'report_version': '2.0',
        'timestamp': timestamp,
        'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'host_info': {k: d.get(k) for k in ['hostname','os','arch','user','motherboard','bios',
            'license_status','license_type','uptime','secure_boot','power_plan']},
        'hardware': {
            'cpu': {k: d.get(k) for k in ['cpu_name','cpu_cores','cpu_threads','cpu_freq','cpu_load']},
            'memory': {'total_gb': d.get('mem_total'), 'used_gb': d.get('mem_used'),
                       'free_gb': d.get('mem_free'), 'usage_pct': d.get('mem_pct'), 'chips': d.get('mem_chips')},
            'disks': d.get('disks'), 'physical_disks': d.get('physical_disks'),
            'gpu': d.get('gpu'), 'gpu_driver': d.get('gpu_driver')
        },
        'network': {
            'adapters': d.get('net_adapters'), 'ipv4': d.get('ipv4_addrs'),
            'gateway': d.get('gateway'), 'dns': d.get('dns'),
            'traffic_rx': d.get('net_rx'), 'traffic_tx': d.get('net_tx'),
            'connections': {'established': d.get('conn_established'), 'listening': d.get('conn_listening'),
                           'time_wait': d.get('conn_timewait')},
            'listen_ports': d.get('listen_ports'), 'shares': d.get('shares')
        },
        'security': {
            'firewall': {'domain': d.get('fw_domain'), 'private': d.get('fw_private'), 'public': d.get('fw_public')},
            'rdp': {'port': d.get('rdp_port'), 'enabled': d.get('rdp_enabled'), 'nla': d.get('rdp_nla')},
            'bitlocker': {'available': d.get('bitlocker_available'), 'drives': d.get('bitlocker')},
            'defender': d.get('defender'), 'audit_available': d.get('audit_available'),
            'time': {'status': d.get('time_status'), 'source': d.get('time_source')},
            'password_policy': d.get('pw_policy'), 'updates': d.get('updates')
        },
        'users': {'local_users': d.get('local_users'), 'admin_members': d.get('admin_members')},
        'processes': {'total': d.get('proc_count'), 'services_running': d.get('svc_running'),
                      'top10_memory': d.get('proc_top10')},
        'startup': {'items': d.get('startup_items'), 'scheduled_tasks': d.get('sched_tasks'),
                    'sched_total': d.get('sched_total')},
        'software': {'count': d.get('sw_count'), 'list': d.get('sw_list')},
        'event_logs': {
            'system': {'total': d.get('log_sys_total'), 'grouped': d.get('log_sys_grouped')},
            'application': {'total': d.get('log_app_total'), 'grouped': d.get('log_app_grouped')}
        },
        'docker': d.get('docker'), 'docker_ps': d.get('docker_ps'),
        'ai': {'npu_devices': d.get('npu'), 'inference_processes': d.get('inference'),
               'inference_ports': d.get('inf_ports')},
        'power': {'battery': d.get('battery'), 'thermal': d.get('thermal'),
                  'thermal_sensors': d.get('thermal_sensors'), 'fans': d.get('fans'),
                  'power_plan': d.get('power_plan')}
    }
    return json.dumps(report, indent=2, ensure_ascii=False, default=str)


def generate_md(d: Dict, timestamp: str) -> str:
    """生成 Markdown 报告"""
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    esc_md = lambda s: str(s).replace('|', '\\|').replace('\n', ' ').strip() if s else 'N/A'
    L = []

    def a(s):
        L.append(s)

    a('# Windows 系统巡检报告')
    a('')
    a('> 生成时间: {} | 主机: {} | 操作系统: {}'.format(today, esc_md(d.get('hostname')), esc_md(d.get('os'))))
    a('')
    a('---')
    a('')

    a('## 一、主机基本信息')
    a('')
    a('| 项目 | 值 |')
    a('|---|---|')
    for label, key in [('计算机名','hostname'),('操作系统','os'),('架构','arch'),('主板','motherboard'),
        ('BIOS','bios'),('许可证','license_status'),('运行时间','uptime'),('安全启动','secure_boot'),('电源计划','power_plan')]:
        a('| {} | {} |'.format(label, esc_md(d.get(key))))
    a('')
    a('---')
    a('')

    a('## 二、硬件资源状态')
    a('')
    a('### CPU')
    a('')
    a('| 型号 | 核心数 | 线程数 | 频率 (MHz) | 使用率 (%) |')
    a('|---|---|---|---|---|')
    a('| {} | {} | {} | {} | {} |'.format(esc_md(d.get('cpu_name')), esc_md(d.get('cpu_cores')),
        esc_md(d.get('cpu_threads')), esc_md(d.get('cpu_freq')), esc_md(d.get('cpu_load'))))
    a('')
    a('### 内存')
    a('')
    a('| 总计 (GB) | 已用 (GB) | 空闲 (GB) | 使用率 |')
    a('|---|---|---|---|')
    a('| {:.1f} | {:.1f} | {:.1f} | {}% |'.format(d.get('mem_total',0), d.get('mem_used',0),
        d.get('mem_free',0), esc_md(d.get('mem_pct'))))
    a('')
    a('### 磁盘存储')
    a('')
    a('| 盘符 | 总容量 (GB) | 已用 (GB) | 可用 (GB) | 使用率 |')
    a('|---|---|---|---|---|')
    for dk in d.get('disks', []):
        a('| {} | {} | {} | {} | {}% |'.format(esc_md(dk.get('drive')), esc_md(dk.get('total')),
            esc_md(dk.get('used')), esc_md(dk.get('free')), esc_md(dk.get('pct'))))
    a('')
    a('---')
    a('')

    a('## 三、网络配置与连接')
    a('')
    a('| 网关 | DNS | 已建立 | 监听 |')
    a('|---|---|---|---|')
    a('| {} | {} | {} | {} |'.format(esc_md(d.get('gateway')), esc_md(d.get('dns')),
        d.get('conn_established',0), d.get('conn_listening',0)))
    a('')
    for p in (d.get('listen_ports') or [])[:15]:
        a('- 端口 {}: {} ({})'.format(p.get('port'), esc_md(p.get('process')), p.get('scope')))
    a('')
    a('---')
    a('')

    a('## 四、安全配置审计')
    a('')
    a('| 防火墙 | RDP |')
    a('|---|---|')
    a('| 域:{} 专用:{} 公用:{} | {} (端口 {}) |'.format(d.get('fw_domain'), d.get('fw_private'),
        d.get('fw_public'), d.get('rdp_enabled'), d.get('rdp_port')))
    a('')
    a('---')
    a('')

    a('## 五、进程与服务')
    a('')
    a('进程总数: {} | 运行中服务: {}'.format(d.get('proc_count',0), esc_md(d.get('svc_running'))))
    a('')
    a('### 内存占用 Top 10')
    a('')
    for i, p in enumerate((d.get('proc_top10') or [])[:10], 1):
        a('{}. {} (PID:{} | {} MB)'.format(i, esc_md(p.get('name')), p.get('pid'), p.get('mem_kb',0)//1024))
    a('')
    a('---')
    a('')

    a('## 六、已安装软件')
    a('')
    a('共 {} 款软件'.format(d.get('sw_count',0)))
    for s in (d.get('sw_list') or [])[:20]:
        a('- {} v{} - {}'.format(esc_md(s.get('name')), esc_md(s.get('ver')), esc_md(s.get('pub'))))
    if len(d.get('sw_list') or []) > 20:
        a('- ... 共 {} 款，仅显示前 20 款'.format(d['sw_count']))
    a('')
    a('---')
    a('')

    a('## 七、Docker')
    docker = d.get('docker', {}) or {}
    if docker.get('available'):
        a('- 版本: {} | 容器: {} | 运行中: {}'.format(esc_md(docker.get('version')),
            docker.get('containers','0'), docker.get('running','0')))
    else:
        a('Docker 未安装或未运行')
    a('')
    a('---')
    a('')

    a('## 八、NPU & AI')
    for n in (d.get('npu') or []):
        a('- NPU: {} ({})'.format(esc_md(n.get('name')), n.get('status')))
    for inf in (d.get('inference') or [])[:5]:
        a('- AI: {} (PID:{} | {}MB)'.format(esc_md(inf.get('name')), inf.get('pid'), inf.get('mem_mb')))
    a('')
    a('---')
    a('')

    a('## 九、电源与散热')
    battery = d.get('battery') or {}
    if battery.get('charge_pct') and battery['charge_pct'] != 'N/A':
        a('- 电量: {}% | {}'.format(battery.get('charge_pct'), battery.get('status')))
    th = d.get('thermal') or {}
    if th.get('cpu_temp'):
        a('- CPU 温度: {}'.format(th['cpu_temp']))
    a('')
    a('---')
    a('')

    a('## 十、风险评估')
    cpu_pct = float(d.get('cpu_load') or 0) if d.get('cpu_load') and d['cpu_load'] != 'N/A' else 0
    mem_pct = d.get('mem_pct', 0)
    max_disk = max((float(dk.get('pct','0').split('\n')[0].strip()) for dk in d.get('disks',[])), default=0)
    issues = []
    if cpu_pct > 90: issues.append(('高','CPU 使用率过高'))
    if mem_pct > 90: issues.append(('高','内存使用率过高'))
    if max_disk > 90: issues.append(('高','磁盘空间不足'))
    if d.get('fw_domain')=='OFF' or d.get('fw_private')=='OFF' or d.get('fw_public')=='OFF':
        issues.append(('高','防火墙未全部开启'))
    risk = '高' if any(i[0]=='高' for i in issues) else '中'
    a('综合风险等级: **{}**'.format(risk if issues else '低'))
    if issues:
        a('')
        a('发现的问题:')
        for lv, desc in issues:
            a('- **[{}]** {}'.format(lv, desc))
    a('')
    a('---')
    a('')
    a('*Report generated at {}*'.format(today))
    a('')
    return '\n'.join(L)


def main():
    """主入口：采集数据 → 生成报告（html/json/md）"""
    output_format = 'html'
    output_file = ''
    verbose = False
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] in ('-f', '--format') and i + 1 < len(sys.argv):
            output_format = sys.argv[i + 1].lower()
            i += 2
        elif sys.argv[i] in ('-o', '--output') and i + 1 < len(sys.argv):
            output_file = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] in ('-v', '--verbose'):
            verbose = True
            i += 1
        elif sys.argv[i] in ('-h', '--help'):
            print('用法: python win_inspection_html.py [选项]')
            print('')
            print('选项:')
            print('  -o FILE          指定报告输出路径')
            print('  -f FORMAT        输出格式: html (默认) | json | md')
            print('  -v, --verbose    详细日志')
            print('  -h, --help       显示此帮助')
            print('')
            print('示例:')
            print('  python win_inspection_html.py')
            print('  python win_inspection_html.py -f json')
            print('  python win_inspection_html.py -f md -o report.md')
            return
        else:
            print('未知参数:', sys.argv[i])
            print('用法: python win_inspection_html.py [-f FORMAT] [-o FILE] [-v] [-h]')
            sys.exit(1)
    if output_format not in ('html', 'json', 'md'):
        print('错误: -f 仅支持 html | json | md')
        sys.exit(1)
    print('=' * 50)
    print('  Windows 系统巡检工具 v2.0')
    print('=' * 50)
    print('正在采集系统数据...')
    d = collect_all()
    print('  主机名:', d['hostname'])
    print('  操作系统:', d['os'])
    print('  内存: %.1f GB' % d['mem_total'])
    print('  磁盘: %d 个分区' % len(d['disks']))
    print('  进程: %d 个' % d['proc_count'])
    print('  软件: %d 款' % d['sw_count'])
    print('  Docker:', '已安装' if d['docker']['available'] else '未安装')
    print('  NPU: %d 个设备' % len(d['npu']))
    print('  AI推理进程: %d 个' % len(d['inference']))
    print('数据采集完成。正在生成 %s 格式报告...' % output_format)
    if verbose:
        print('  采集条目数: %d' % len(d))
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    if output_format == 'html':
        content = generate_html(d, timestamp)
        ext = 'html'
    elif output_format == 'json':
        content = generate_json(d, timestamp)
        ext = 'json'
    else:
        content = generate_md(d, timestamp)
        ext = 'md'
    if output_file:
        filename = output_file
    else:
        filename = 'System_Inspection_Report_' + timestamp + '.' + ext
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    print()
    print('报告已生成:', filename)
    print('文件大小: %d 字符' % len(content))
    return filename

if __name__ == '__main__':
    main()
