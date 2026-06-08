# HTML 报告风格指南

## 设计规范

### 整体风格：玻璃态深色/浅色双主题

基于 Tailwind CSS 的 glass-card / glass-panel 组件系统。

### 颜色系统

| 用途 | 深色模式 | 浅色模式 |
|------|---------|---------|
| 背景 | `#0a0f1c → #0c1222` 渐变 | `#f1f5f9` 纯色 |
| 卡片背景 | `rgba(15,23,42,0.7)` + blur | `rgba(255,255,255,0.85)` + blur |
| 面板背景 | `rgba(30,41,59,0.5)` | `rgba(255,255,255,0.7)` |
| 边框 | `rgba(59,130,246,0.3)` | `rgba(100,116,139,0.2)` |
| 主文字 | `#e2e8f0` | `#0f172a` |
| 次文字 | `#94a3b8` | `#475569` |

### 组件类名

```css
.glass-card   /* 玻璃卡片 - 用于顶部栏、按钮 */
.glass-panel  /* 玻璃面板 - 用于数据区域 */
.hover-grow   /* 悬停上浮效果 */
```

### 图表配色（双设备对比）

| 设备A (GB10) | 设备B (昇腾) |
|-------------|-------------|
| 边框: `#34d399` (绿) | 边框: `#22d3ee` (青) |
| 填充: `rgba(52,211,153,0.1)` | 填充: `rgba(34,211,238,0.1)` |
| 柱状: `rgba(52,211,153,0.6)` | 柱状: `rgba(34,211,238,0.6)` |

### 单设备图表配色

- 吞吐曲线: `#3b82f6` (蓝)
- 延迟曲线: `#f97316` (橙)
- TTFT: `#06b6d4` (青)
- TPOT: `#8b5cf6` (紫)

### 离线资源依赖

HTML 报告引用的本地资源（全部放在 `assets/` 目录下）：

| 文件 | 大小 | 用途 |
|------|------|------|
| `inter-font.css` | ~2.1MB | Inter 字体 (base64 data URI) |
| `tailwind.min.js` | ~407KB | Tailwind CSS CDN 离线版 |
| `chart.umd.min.js` | ~205KB | Chart.js 图表库 |
| `fontawesome.min.css` | ~2.1MB | FontAwesome 图标 (base64 SVG) |
| `marked.min.js` | ~40KB | Markdown 渲染（硬件信息弹窗） |

> **离线策略**: 字体和图标使用 base64 data URI 嵌入，避免 `file://` 协议的跨域限制。

### 主题切换

```javascript
// 初始化
const theme = localStorage.getItem('theme') || 'dark';
document.body.setAttribute('data-theme', theme);

// 切换
document.getElementById('themeToggle').addEventListener('click', () => {
    const t = body.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.body.setAttribute('data-theme', t);
    localStorage.setItem('theme', t);
    // 重新初始化 Chart.js 图表（更新颜色）
    initCharts(t);
});
```

### Chart.js 通用配置

```javascript
function commonOpts(colors, yTitle, xTitle) {
    return {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: { labels: { color: colors.label, usePointStyle: true } },
            tooltip: { mode: 'index', intersect: false }
        },
        scales: {
            y: { title: { display: true, text: yTitle, color: colors.title },
                 grid: { color: colors.grid }, ticks: { color: colors.label } },
            x: { title: { display: true, text: xTitle, color: colors.title },
                 grid: { color: colors.grid }, ticks: { color: colors.label } }
        }
    };
}
```

### 响应式布局

- 最大宽度: `max-w-7xl mx-auto`
- 卡片网格: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`
- 图表网格: `grid-cols-1 lg:grid-cols-2`
- 表格: `overflow-x-auto` + `min-w-full`

## 页面结构（单设备报告）

1. 顶部操作按钮（导出Word / 硬件信息 / 主题切换）
2. 报告元信息（标题 + 日期 + 工具 + 模型 + 标签）
3. 被测设备 + 被测模型（双列卡片）
4. 核心性能指标卡片（TTFT / TPOT / 吞吐 / E2E延迟）
5. 可视化图表（并发-吞吐 / 时延随并发变化）
6. 逐组测试明细表
7. 电子签署行

## 页面结构（比对报告）

1. 顶部操作按钮（导出Excel / 主题切换）
2. 报告元信息（标题 + 日期 + 工具 + 标签）
3. 设备与环境对比（双列卡片 A vs B）
4. 核心指标对比卡片（4项指标 + 结论）
5. 6张对比图表（延迟/吞吐/TTFT/QPS/输出Token/请求数）
6. 逐组对比明细（Tab切换：合并/A详情/B详情）
7. 汇总统计表
8. 性能分析结论（结论卡片列表）
9. 电子签署行

## 命名规范

- 文件名前缀: `deeprunner_`
- 单设备报告: `deeprunner_<设备名>测评报告.html`
- 比对报告: `deeprunner_推理性能比对报告_<A>_vs_<B>.html`
- Excel: `DeepRunner_推理性能比对报告_<A>_vs_<B>.xlsx`
