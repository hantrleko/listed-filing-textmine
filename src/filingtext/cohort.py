"""跨行业验收集：3 个行业 × 5 家 × 3 年。只定义名单，不包含年报正文。"""

from __future__ import annotations

VALIDATION_YEARS = (2022, 2023, 2024)

COHORT = [
    {"industry": "白酒", "ticker": "600519", "firm_name": "贵州茅台"},
    {"industry": "白酒", "ticker": "000858", "firm_name": "五粮液"},
    {"industry": "白酒", "ticker": "000568", "firm_name": "泸州老窖"},
    {"industry": "白酒", "ticker": "600809", "firm_name": "山西汾酒"},
    {"industry": "白酒", "ticker": "000596", "firm_name": "古井贡酒"},
    {"industry": "银行", "ticker": "600036", "firm_name": "招商银行"},
    {"industry": "银行", "ticker": "601398", "firm_name": "工商银行"},
    {"industry": "银行", "ticker": "601288", "firm_name": "农业银行"},
    {"industry": "银行", "ticker": "600000", "firm_name": "浦发银行"},
    {"industry": "银行", "ticker": "000001", "firm_name": "平安银行"},
    {"industry": "医药", "ticker": "600276", "firm_name": "恒瑞医药"},
    {"industry": "医药", "ticker": "000538", "firm_name": "云南白药"},
    {"industry": "医药", "ticker": "300760", "firm_name": "迈瑞医疗"},
    {"industry": "医药", "ticker": "600196", "firm_name": "复星医药"},
    {"industry": "医药", "ticker": "000661", "firm_name": "长春高新"},
]


def cohort_jobs(years: tuple[int, ...] = VALIDATION_YEARS) -> list[dict]:
    jobs = []
    for firm in COHORT:
        for year in years:
            jobs.append({**firm, "fiscal_year": year})
    return jobs
