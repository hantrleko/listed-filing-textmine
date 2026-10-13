"""合成年报，只用于打通管线，不是真实披露。"""

from __future__ import annotations

SAMPLE_DOCS = [
    {
        "filename": "000001_2022_annual.txt",
        "market": "CN",
        "ticker": "000001",
        "firm_name": "示例银行股份有限公司",
        "fiscal_year": 2022,
        "report_type": "annual",
        "text": """示例银行股份有限公司2022年年度报告

目录
第三节 管理层讨论与分析 .......... 3
第四节 公司治理 .......... 8

第三节 管理层讨论与分析
报告期内，公司营业收入保持增长，主业盈利能力稳健。公司持续推进节能减排和清洁生产，环保投入有所提升。国际贸易摩擦和关税政策对部分出口业务形成扰动，管理层对地缘政治保持关注。公司信息系统运行平稳，自动化改造按计划实施。董事会认为经营状况良好。
社会责任
公司在本节补充说明了环境管理进展，该句应仍留在管理层讨论中。

第四节 公司治理
报告期内公司治理结构保持稳定，董事会运作规范，本段不应进入管理层讨论。
""",
    },
    {
        "filename": "000001_2023_annual.txt",
        "market": "CN",
        "ticker": "000001",
        "firm_name": "示例银行股份有限公司",
        "fiscal_year": 2023,
        "report_type": "annual",
        "text": """示例银行股份有限公司2023年年度报告

目录
第三节 管理层讨论与分析 .......... 3
第四节 公司治理 .......... 9

第三节 管理层讨论与分析
报告期内，公司营业收入保持增长，盈利水平改善。公司围绕碳达峰与碳中和推进绿色转型，加大可再生能源使用，并披露温室气体排放强度。公司持续推进节能减排和清洁生产，环保投入有所提升。与此同时，公司加快数字化转型，建设工业互联网与数据中台，在质检环节试点人工智能和机器学习。出口管制、实体清单和供应链中断等地缘风险上升，关税与制裁压力加大。董事会认为经营状况良好，但相关业务承压。

第四节 公司治理
报告期内公司治理结构保持稳定，董事会运作规范，本段不应进入管理层讨论。
""",
    },
    {
        "filename": "000001_2024_annual.txt",
        "market": "CN",
        "ticker": "000001",
        "firm_name": "示例银行股份有限公司",
        "fiscal_year": 2024,
        "report_type": "annual",
        "text": """示例银行股份有限公司2024年年度报告

第三节 管理层讨论与分析
报告期内，需求下滑，收入下降，部分资产出现减值，盈利承压。绿色转型仍在推进，但环保设施投产推迟。数智化项目延期，大模型应用尚未形成收入，人工智能投入短期没有改善盈利。地缘冲突与贸易战延续，供应链重构增加成本，经营不确定性上升。公司对出口管制保持跟踪。董事会认为挑战加大。

第四节 公司治理
报告期内公司治理结构保持稳定，本段不应进入管理层讨论。
""",
    },
    {
        "filename": "600001_2022_annual.txt",
        "market": "CN",
        "ticker": "600001",
        "firm_name": "示例制造股份有限公司",
        "fiscal_year": 2022,
        "report_type": "annual",
        "text": """示例制造股份有限公司2022年年度报告

第三节 管理层讨论与分析
报告期内，公司订单保持增长，盈利能力稳健。生产环节完成自动化改造，信息系统覆盖主要车间。公司推进清洁生产和节能减排，环保投入略有提升。关税调整对出口设备形成扰动，管理层开始关注地缘政治。

第四节 重要事项
本段属于重要事项，不应进入管理层讨论。
""",
    },
    {
        "filename": "600001_2023_annual.txt",
        "market": "CN",
        "ticker": "600001",
        "firm_name": "示例制造股份有限公司",
        "fiscal_year": 2023,
        "report_type": "annual",
        "text": """示例制造股份有限公司2023年年度报告

第三节 管理层讨论与分析
报告期内，公司订单保持增长，盈利能力改善。生产环节在自动化之外试点人工智能、机器学习和工业互联网，并建设数据中台推进数字化转型。公司推进清洁生产、节能减排和绿色转型，开始核算温室气体排放强度。出口管制与关税并存，供应链中断使交付承压，地缘政治影响上升。

第四节 重要事项
本段属于重要事项，不应进入管理层讨论。
""",
    },
    {
        "filename": "NWND_2022_10K.txt",
        "market": "US",
        "ticker": "NWND",
        "firm_name": "NORTHWIND DEVICES INC.",
        "fiscal_year": 2022,
        "report_type": "10-K",
        "text": """UNITED STATES
SECURITIES AND EXCHANGE COMMISSION
Form 10-K
For the fiscal year ended December 31, 2022
NORTHWIND DEVICES INC.

TABLE OF CONTENTS
ITEM 1A. RISK FACTORS  3
ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS  5
ITEM 8. FINANCIAL STATEMENTS  9

ITEM 1A. RISK FACTORS
We face geopolitical risk. Tariffs, sanctions, and export controls may disrupt suppliers. A trade war or regional conflict could increase costs. These risk factors are specific to the risk section.

ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS
Revenue increased and profitability improved. Results were strong, and operating efficiency supported earnings growth. We continued a limited digital transformation and maintained our information system. Climate-related compliance costs were stable. The company reported no material impairment.

ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA
The consolidated balance sheet is omitted from this synthetic filing and must not enter the MD&A.
""",
    },
    {
        "filename": "NWND_2023_10K.txt",
        "market": "US",
        "ticker": "NWND",
        "firm_name": "NORTHWIND DEVICES INC.",
        "fiscal_year": 2023,
        "report_type": "10-K",
        "text": """UNITED STATES
SECURITIES AND EXCHANGE COMMISSION
Form 10-K
For the fiscal year ended December 31, 2023
NORTHWIND DEVICES INC.

TABLE OF CONTENTS
ITEM 1A. RISK FACTORS  4
ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS  6
ITEM 8. FINANCIAL STATEMENTS  10

ITEM 1A. RISK FACTORS
We face geopolitical risk. Tariffs, sanctions, export controls, and an entity list designation may disrupt the supply chain. A trade war, decoupling pressure, and regional conflict remain risk factors in this risk section.

ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS
Revenue increased, but an inventory impairment and a demand disruption weakened results. Profitability improved in the service segment, while the hardware segment reported a loss. We invested in artificial intelligence, machine learning, and cloud computing as part of a broader digital transformation. Climate risk and greenhouse gas compliance costs rose. Geopolitical risk is discussed under risk factors.

ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA
The consolidated balance sheet is omitted from this synthetic filing and must not enter the MD&A.
""",
    },
]
