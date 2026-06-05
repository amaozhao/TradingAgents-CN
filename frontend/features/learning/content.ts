import fs from "node:fs/promises"
import path from "node:path"

export interface LearningArticle {
  id: string
  title: string
  category: string
  categoryTitle: string
  description: string
  readTime: string
  difficulty: "入门" | "进阶" | "高级"
  views: number
  file?: string
  externalUrl?: string
}

export interface LearningCategory {
  id: string
  title: string
  icon: string
  description: string
}

export const learningCategories: LearningCategory[] = [
  { id: "ai-basics", title: "AI基础知识", icon: "AI", description: "从零开始了解人工智能和大语言模型的基本概念" },
  { id: "prompt-engineering", title: "提示词工程", icon: "PE", description: "学习如何编写高质量的提示词，让AI更好地理解你的需求" },
  { id: "model-selection", title: "模型选择指南", icon: "MS", description: "了解不同大模型的特点，选择最适合你的模型" },
  { id: "analysis-principles", title: "AI分析股票原理", icon: "MA", description: "深入了解多智能体如何协作分析股票" },
  { id: "risks-limitations", title: "风险与局限性", icon: "RK", description: "了解AI的潜在问题和正确使用方式" },
  { id: "resources", title: "架构与论文", icon: "RP", description: "AGENTrader架构介绍和学术论文资源" },
  { id: "tutorials", title: "实战教程", icon: "TU", description: "通过实际案例学习如何使用本工具" },
  { id: "faq", title: "常见问题", icon: "QA", description: "快速找到常见问题的答案" }
]

export const learningArticles: LearningArticle[] = [
  { id: "what-is-llm", title: "什么是大语言模型（LLM）？", category: "ai-basics", categoryTitle: "AI基础知识", description: "深入了解大语言模型的定义、工作原理和在股票分析中的应用", readTime: "10分钟", difficulty: "入门", views: 2345, file: "docs/learning/01-ai-basics/what-is-llm.md" },
  { id: "prompt-basics", title: "提示词基础", category: "prompt-engineering", categoryTitle: "提示词工程", description: "学习提示词的基本概念、结构和编写技巧", readTime: "10分钟", difficulty: "入门", views: 1876, file: "docs/learning/02-prompt-engineering/prompt-basics.md" },
  { id: "best-practices", title: "提示词工程最佳实践", category: "prompt-engineering", categoryTitle: "提示词工程", description: "掌握提示词编写的核心原则和实用技巧", readTime: "12分钟", difficulty: "进阶", views: 1543, file: "docs/learning/02-prompt-engineering/best-practices.md" },
  { id: "model-comparison", title: "大语言模型对比与选择", category: "model-selection", categoryTitle: "模型选择指南", description: "对比主流大语言模型的特点，学会选择最适合的模型", readTime: "15分钟", difficulty: "进阶", views: 1987, file: "docs/learning/03-model-selection/model-comparison.md" },
  { id: "multi-agent-system", title: "多智能体系统详解", category: "analysis-principles", categoryTitle: "AI分析股票原理", description: "深入理解AGENTrader的多智能体协作机制", readTime: "15分钟", difficulty: "进阶", views: 1654, file: "docs/learning/04-analysis-principles/multi-agent-system.md" },
  { id: "risk-warnings", title: "AI股票分析的风险与局限性", category: "risks-limitations", categoryTitle: "风险与局限性", description: "了解AI的主要局限性、使用风险和正确的使用方式", readTime: "12分钟", difficulty: "入门", views: 2134, file: "docs/learning/05-risks-limitations/risk-warnings.md" },
  { id: "agentrader_intro", title: "AGENTrader架构介绍", category: "resources", categoryTitle: "架构与论文", description: "了解AGENTrader的多智能体架构和核心特性", readTime: "15分钟", difficulty: "进阶", views: 1432, file: "docs/learning/06-resources/agentrader_intro.md" },
  { id: "paper-guide", title: "AGENTrader论文解读", category: "resources", categoryTitle: "架构与论文", description: "解读多智能体金融分析论文的核心内容和实践启发", readTime: "20分钟", difficulty: "高级", views: 987, file: "docs/learning/06-resources/paper-guide.md" },
  { id: "AGENTrader_论文中文版", title: "AGENTrader 论文中文版", category: "resources", categoryTitle: "架构与论文", description: "多智能体金融分析框架论文中文翻译", readTime: "40分钟", difficulty: "高级", views: 860, file: "docs/paper/AGENTrader_论文中文版.md" },
  { id: "getting-started", title: "快速入门教程", category: "tutorials", categoryTitle: "实战教程", description: "从零开始学习如何使用AGENTrader进行股票分析", readTime: "10分钟", difficulty: "入门", views: 3456, externalUrl: "https://mp.weixin.qq.com/s/uAk4RevdJHMuMvlqpdGUEw" },
  { id: "usage-guide-preview", title: "使用指南（试用版）", category: "tutorials", categoryTitle: "实战教程", description: "AGENTrader 使用指南与试用说明", readTime: "15分钟", difficulty: "入门", views: 1288, externalUrl: "https://mp.weixin.qq.com/s/ppsYiBncynxlsfKFG8uEbw" },
  { id: "general-questions", title: "常见问题解答", category: "faq", categoryTitle: "常见问题", description: "关于功能、模型选择、使用技巧等常见问题的答案", readTime: "15分钟", difficulty: "入门", views: 2876, file: "docs/learning/08-faq/general-questions.md" }
]

export function getCategory(id: string) {
  return learningCategories.find((category) => category.id === id)
}

export function getArticle(id: string) {
  return learningArticles.find((article) => article.id === id)
}

export function getArticlesByCategory(category: string) {
  return learningArticles.filter((article) => article.category === category)
}

export async function readArticleMarkdown(article: LearningArticle) {
  if (!article.file) return ""
  const repoRoot = path.resolve(process.cwd(), "..")
  return fs.readFile(path.join(repoRoot, article.file), "utf8")
}
