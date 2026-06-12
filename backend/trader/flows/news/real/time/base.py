from .imports import List, ZoneInfo, datetime, get_timezone_name, logger
from .setup import NewsItem

class _RealtimeNewsAggregatorMixin2:
    def _deduplicate_news(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """去重新闻"""
        logger.info(f"[新闻去重] 开始对 {len(news_items)} 条新闻进行去重处理")
        start_time = datetime.now(ZoneInfo(get_timezone_name()))

        seen_titles = set()
        unique_news = []
        duplicate_count = 0
        short_title_count = 0

        for item in news_items:
            # 简单的标题去重
            title_key = item.title.lower().strip()

            # 检查标题长度
            if len(title_key) <= 10:
                logger.debug(f"[新闻去重] 跳过标题过短的新闻: '{item.title}'，来源: {item.source}")
                short_title_count += 1
                continue

            # 检查是否重复
            if title_key in seen_titles:
                logger.debug(f"[新闻去重] 检测到重复新闻: '{item.title[:50]}...'，来源: {item.source}")
                duplicate_count += 1
                continue

            # 添加到结果集
            seen_titles.add(title_key)
            unique_news.append(item)

        # 记录去重结果
        time_taken = (datetime.now(ZoneInfo(get_timezone_name())) - start_time).total_seconds()
        logger.info(f"[新闻去重] 去重完成，原始新闻: {len(news_items)}条，去重后: {len(unique_news)}条，")
        logger.info(
            f"[新闻去重] 去除重复: {duplicate_count}条，标题过短: {short_title_count}条，耗时: {time_taken:.2f}秒"
        )

        return unique_news

    def format_news_report(self, news_items: List[NewsItem], ticker: str) -> str:
        """格式化新闻报告"""
        logger.info(f"[新闻报告] 开始为 {ticker} 生成新闻报告")
        start_time = datetime.now(ZoneInfo(get_timezone_name()))

        if not news_items:
            logger.warning(f"[新闻报告] 未获取到 {ticker} 的实时新闻数据")
            return f"未获取到{ticker}的实时新闻数据。"

        # 按紧急程度分组
        high_urgency = [n for n in news_items if n.urgency == "high"]
        medium_urgency = [n for n in news_items if n.urgency == "medium"]
        low_urgency = [n for n in news_items if n.urgency == "low"]

        # 记录新闻分类情况
        logger.info(
            f"[新闻报告] {ticker} 新闻分类统计: 高紧急度 {len(high_urgency)}条, 中紧急度 {len(medium_urgency)}条, 低紧急度 {len(low_urgency)}条"
        )

        # 记录新闻来源分布
        news_sources = {}
        for item in news_items:
            source = item.source
            if source in news_sources:
                news_sources[source] += 1
            else:
                news_sources[source] = 1

        sources_info = ", ".join([f"{source}: {count}条" for source, count in news_sources.items()])
        logger.info(f"[新闻报告] {ticker} 新闻来源分布: {sources_info}")

        report = f"# {ticker} 实时新闻分析报告\n\n"
        report += f"📅 生成时间: {datetime.now(ZoneInfo(get_timezone_name())).strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"📊 新闻总数: {len(news_items)}条\n\n"

        if high_urgency:
            report += "## 🚨 紧急新闻\n\n"
            for news in high_urgency[:3]:  # 最多显示3条
                report += f"### {news.title}\n"
                report += f"**来源**: {news.source} | **时间**: {news.publish_time.strftime('%H:%M')}\n"
                report += f"{news.content}\n\n"

        if medium_urgency:
            report += "## 📢 重要新闻\n\n"
            for news in medium_urgency[:5]:  # 最多显示5条
                report += f"### {news.title}\n"
                report += f"**来源**: {news.source} | **时间**: {news.publish_time.strftime('%H:%M')}\n"
                report += f"{news.content}\n\n"

        # 添加时效性说明
        latest_news = max(news_items, key=lambda x: x.publish_time)
        time_diff = datetime.now(ZoneInfo(get_timezone_name())) - latest_news.publish_time

        report += "\n## ⏰ 数据时效性\n"
        report += f"最新新闻发布于: {time_diff.total_seconds() / 60:.0f}分钟前\n"

        if time_diff.total_seconds() < 1800:  # 30分钟内
            report += "🟢 数据时效性: 优秀 (30分钟内)\n"
        elif time_diff.total_seconds() < 3600:  # 1小时内
            report += "🟡 数据时效性: 良好 (1小时内)\n"
        else:
            report += "🔴 数据时效性: 一般 (超过1小时)\n"

        # 记录报告生成完成信息
        end_time = datetime.now(ZoneInfo(get_timezone_name()))
        time_taken = (end_time - start_time).total_seconds()
        report_length = len(report)

        logger.info(f"[新闻报告] {ticker} 新闻报告生成完成，耗时: {time_taken:.2f}秒，报告长度: {report_length}字符")

        # 记录时效性信息
        time_diff_minutes = time_diff.total_seconds() / 60
        logger.info(f"[新闻报告] {ticker} 新闻时效性: 最新新闻发布于 {time_diff_minutes:.1f}分钟前")

        return report
