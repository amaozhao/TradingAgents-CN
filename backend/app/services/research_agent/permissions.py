from __future__ import annotations


MARKET_DATA_READ = "research.market_data.read"
SCREENING_RUN = "research.screening.run"
SINGLE_STOCK_ANALYSIS = "research.analysis.single"
BATCH_STOCK_ANALYSIS = "research.analysis.batch"
REPORT_READ = "research.report.read"
REPORT_WRITE = "research.report.write"
ALPHA_READ = "research.alpha.read"
ALPHA_RUN = "research.alpha.run"
CORRELATION_RUN = "research.correlation.run"
ADMIN_CONFIG_WRITE = "admin.config.write"


def normal_user_permissions() -> frozenset[str]:
    return frozenset(
        {
            MARKET_DATA_READ,
            SCREENING_RUN,
            SINGLE_STOCK_ANALYSIS,
            BATCH_STOCK_ANALYSIS,
            REPORT_READ,
            REPORT_WRITE,
            ALPHA_READ,
            ALPHA_RUN,
            CORRELATION_RUN,
        }
    )


def admin_permissions() -> frozenset[str]:
    return frozenset({ADMIN_CONFIG_WRITE})
