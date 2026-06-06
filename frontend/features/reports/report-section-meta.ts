export type ReportSectionGroupKey =
  | "overview"
  | "core"
  | "debate"
  | "risk"
  | "decision"
  | "raw"

export interface ReportSectionMeta {
  key: string
  group: ReportSectionGroupKey
  order: number
  zhTitle: string
  enTitle: string
  description: string
  aliasOf?: string
}

export interface ReportSectionItem {
  key: string
  title: string
  enTitle: string
  description: string
  content: string | Record<string, unknown>
  group: ReportSectionGroupKey
  order: number
}

export interface ReportSectionGroup {
  key: ReportSectionGroupKey
  title: string
  enTitle: string
  description: string
  sections: ReportSectionItem[]
}

export const reportGroupMeta: Record<
  ReportSectionGroupKey,
  { title: string; enTitle: string; description: string; order: number }
> = {
  overview: {
    title: "总览",
    enTitle: "Overview",
    description: "先看摘要和最终结论，快速判断这份报告的核心立场。",
    order: 10
  },
  core: {
    title: "核心报告",
    enTitle: "Core Reports",
    description: "市场、基本面、新闻和情绪等基础分析材料。",
    order: 20
  },
  debate: {
    title: "多方辩论",
    enTitle: "Research Debate",
    description: "看涨和看跌研究员的主要论证。",
    order: 30
  },
  risk: {
    title: "风险评审",
    enTitle: "Risk Review",
    description: "保守、中立和激进风险视角的交叉检查。",
    order: 40
  },
  decision: {
    title: "决策链路",
    enTitle: "Decision Flow",
    description: "从研究结论、交易计划到风控裁决的完整链路。",
    order: 50
  },
  raw: {
    title: "原始内容",
    enTitle: "Raw Sections",
    description: "尚未纳入标准展示结构的报告片段。",
    order: 90
  }
}

export const reportSectionMeta: Record<string, ReportSectionMeta> = {
  final_trade_decision: {
    key: "final_trade_decision",
    group: "overview",
    order: 10,
    zhTitle: "最终交易决策",
    enTitle: "Final Trade Decision",
    description: "风控委员会主席给出的最终可执行结论。"
  },
  market_report: {
    key: "market_report",
    group: "core",
    order: 10,
    zhTitle: "市场分析",
    enTitle: "Market Analysis",
    description: "价格、成交量、趋势和技术指标。"
  },
  fundamentals_report: {
    key: "fundamentals_report",
    group: "core",
    order: 20,
    zhTitle: "基本面分析",
    enTitle: "Fundamental Analysis",
    description: "公司、估值、财务和行业信息。"
  },
  news_report: {
    key: "news_report",
    group: "core",
    order: 30,
    zhTitle: "新闻分析",
    enTitle: "News Analysis",
    description: "近期新闻和公告影响。"
  },
  sentiment_report: {
    key: "sentiment_report",
    group: "core",
    order: 40,
    zhTitle: "情绪分析",
    enTitle: "Sentiment Analysis",
    description: "市场情绪和舆情信号。"
  },
  bull_researcher: {
    key: "bull_researcher",
    group: "debate",
    order: 10,
    zhTitle: "看涨研究员",
    enTitle: "Bull Researcher",
    description: "支持买入或增持的核心论证。"
  },
  bear_researcher: {
    key: "bear_researcher",
    group: "debate",
    order: 20,
    zhTitle: "看跌研究员",
    enTitle: "Bear Researcher",
    description: "反对买入或提示下行风险的核心论证。"
  },
  safe_analyst: {
    key: "safe_analyst",
    group: "risk",
    order: 10,
    zhTitle: "保守风险分析师",
    enTitle: "Conservative Risk Analyst",
    description: "偏重资金安全和止损边界。"
  },
  neutral_analyst: {
    key: "neutral_analyst",
    group: "risk",
    order: 20,
    zhTitle: "中立风险分析师",
    enTitle: "Neutral Risk Analyst",
    description: "平衡机会与风险的折中视角。"
  },
  risky_analyst: {
    key: "risky_analyst",
    group: "risk",
    order: 30,
    zhTitle: "激进风险分析师",
    enTitle: "Aggressive Risk Analyst",
    description: "偏重收益弹性和机会窗口。"
  },
  research_team_decision: {
    key: "research_team_decision",
    group: "decision",
    order: 10,
    zhTitle: "研究团队结论",
    enTitle: "Research Team Decision",
    description: "研究团队综合多空观点后的建议。"
  },
  investment_plan: {
    key: "investment_plan",
    group: "decision",
    order: 11,
    zhTitle: "研究团队结论",
    enTitle: "Research Team Decision",
    description: "研究团队综合多空观点后的建议。",
    aliasOf: "research_team_decision"
  },
  trader_investment_plan: {
    key: "trader_investment_plan",
    group: "decision",
    order: 20,
    zhTitle: "交易执行计划",
    enTitle: "Trader Execution Plan",
    description: "交易员给出的动作、仓位和执行理由。"
  },
  risk_management_decision: {
    key: "risk_management_decision",
    group: "decision",
    order: 30,
    zhTitle: "风控委员会决议",
    enTitle: "Risk Committee Decision",
    description: "风控委员会对交易计划的裁决。"
  }
}

export function getReportSectionMeta(key: string): ReportSectionMeta {
  return (
    reportSectionMeta[key] ?? {
      key,
      group: "raw",
      order: 1000,
      zhTitle: humanizeReportKey(key),
      enTitle: humanizeReportKey(key),
      description: "未识别的原始报告片段。"
    }
  )
}

export function buildReportSectionGroups(
  reports: Record<string, string | Record<string, unknown>>
): ReportSectionGroup[] {
  const canonicalKeys = new Set(Object.keys(reports))
  const seenContent = new Set<string>()
  const items: ReportSectionItem[] = []

  Object.entries(reports)
    .map(([key, content], index) => ({
      key,
      content,
      index,
      meta: getReportSectionMeta(key)
    }))
    .sort(
      (left, right) =>
        reportGroupMeta[left.meta.group].order - reportGroupMeta[right.meta.group].order ||
        left.meta.order - right.meta.order ||
        left.index - right.index
    )
    .forEach(({ key, content, index, meta }) => {
      if (meta.aliasOf && canonicalKeys.has(meta.aliasOf)) return

      const contentFingerprint = stableContentFingerprint(content)
      if (seenContent.has(contentFingerprint)) return
      seenContent.add(contentFingerprint)

      items.push({
        key,
        title: meta.zhTitle,
        enTitle: meta.enTitle,
        description: meta.description,
        content,
        group: meta.group,
        order: meta.order + index / 1000
      })
    })

  return (Object.keys(reportGroupMeta) as ReportSectionGroupKey[])
    .map((groupKey) => {
      const groupSections = items
        .filter((item) => item.group === groupKey)
        .sort((left, right) => left.order - right.order)
      const groupMeta = reportGroupMeta[groupKey]

      return {
        key: groupKey,
        title: groupMeta.title,
        enTitle: groupMeta.enTitle,
        description: groupMeta.description,
        sections: groupSections
      }
    })
    .filter((group) => group.sections.length > 0)
    .sort(
      (left, right) => reportGroupMeta[left.key].order - reportGroupMeta[right.key].order
    )
}

function humanizeReportKey(key: string) {
  return key
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

function stableContentFingerprint(content: string | Record<string, unknown>) {
  return typeof content === "string" ? content.trim() : JSON.stringify(content)
}
