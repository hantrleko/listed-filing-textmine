# 上市公司非结构化文本挖掘与学术特征提取引擎

把 A 股年报、美股 10-K/10-Q 切成 MD&A / 风险因素，并导出公司-年度面板（Parquet、Stata、DuckDB）。

这是研究管线，不是投资建议。仓库里的词表是可编辑种子词。英文语气若要对齐 Loughran-McDonald，请自行放入官方主词典，不要把本仓库的种子词写成官方词表。

## 安装

```powershell
cd F:\listed-filing-textmine
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
```

FinBERT 是可选项，不装也能跑词典法：

```powershell
pip install -e ".[finbert]"
```

## 在网页里做自己的表

```powershell
streamlit run app/dashboard.py
```

左侧「我的面板」可以按代码和年份抓取，或上传已有 PDF / HTML。结果写到 `data/workspace/output/`，不会改样本案例里的数字。网页单次最多下载 8 份。更大的样本：

```powershell
python scripts/build_factor_panel.py --codes 600519,600276,600887 --start 2022 --end 2024 --out data/factor_panel
```

`data/factor_panel/output/panel_factor.dta` 用因子工作台的主键：`ticker`、`fiscal_year`、`fiscal_quarter`、`available_date`。年报的 `fiscal_quarter` 为 4。`available_date` 是巨潮公告日，等于 `filing_date`，不是报告期期末。东财 `NOTICE_DATE` 和巨潮公告日可能差一天，对不上时不要改用 `fiscal_year` 单独合并。`pit_ready=0` 表示没有公告日。文本过短或边界可疑时，每千词和语气比率为空，计数仍在。

源码：https://github.com/hantrleko/listed-filing-textmine 。词典版本写在 `data_version` / 因子表的 `dictionary_version`。

长表是一章一行。`panel_wide.dta` 是一行一个公司—年度：`mda_*` 与 `risk_*` 分开，A 股 `stkcd` 为 6 位字符串。A 股的 `risk` 取 MD&A 中风险小节到下一个同级标题之间的文字，没有这一标题时 `risk_found` 为 0。

美股抓取要在页面里填写联系邮箱，只保存在本次会话。

## 先跑通示例面板

示例文本是合成的，用来检查切分和字段，不能当真实披露。

```powershell
python -m filingtext.demo
streamlit run app/dashboard.py
```

输出在 `data/output/`：

- `panel.parquet` / `panel.dta` / `panel.duckdb`
- `diagnostics.json`：样本量、分市场覆盖、指标均值和分位数
- `trend_by_year.csv` 与 `trends.png`

看板有四块：词典高亮、词云、章节标题诊断、面板时序。临时词写在侧栏即可验证，不必先改词表文件。

## 批量解析

文件名建议 `{代码}_{年份}_{类型}`，例如 `000001_2023_annual.pdf`、`AAPL_2023_10K.htm`。目录里如果有 `manifest.csv`，会优先用它的代码、公司名、年份和市场。

```powershell
python scripts/batch_parse.py --input data/raw --workers 4 --output data/output
```

常用参数：

- `--market CN|US|AUTO`
- `--sections mda,risk`：A 股默认只取 `mda`；美股 10-K 默认 `mda` 与 `risk`
- `--lm D:\LM\LoughranMcDonald_MasterDictionary.csv`：用官方主词典覆盖英文语气
- `--finbert`：只对英文章节附加 FinBERT-tone 概率。长文按 800 字分块取均值，不是全文一次编码

多进程的解析函数在 `filingtext.parse_job`，不要把工人函数写进 `scripts/batch_parse.py`，否则 Windows 会反复启动自身。

## 抓取原文

巨潮不需要密钥。SEC 要求 User-Agent 里带联系邮箱。

```powershell
python scripts/fetch_reports.py cninfo --codes 000001,600519 --start 2022 --end 2024 --out data/raw
$env:EDGAR_USER_AGENT = "YourName your.email@university.edu"
python scripts/fetch_reports.py edgar --tickers AAPL --start 2022 --end 2024 --forms 10-K,10-Q --out data/raw
```

下载结果会追加到该目录的 `manifest.csv`。请自行控制频率；脚本在请求之间留有间隔。

## 章节怎么切

A 股识别「第X节」标题。`管理层讨论与分析` 优先于 `经营情况讨论与分析` 和旧格式的 `董事会报告`。目录行（点线或行末页码）不当正文起点。`社会责任` 这种没有「第X节」的小节标题不会把 MD&A 截断。

美股 10-K：`Item 1A` 为风险因素，`Item 7` 为 MD&A，在下一个 Item 处结束。10-Q 使用另一套编号：`Item 2` 才是 MD&A。文件名或正文出现 `10-Q` 时会自动切换。

PDF 会丢掉页眉页脚区域，并去掉跨页重复的短行和数字密集的表格行。

## 指标定义

内容词：中文为 jieba 词（已加入领域词），英文为字母词。标点和纯数字不计。

- `esg_count` / `digital_count` / `geopol_count`：词表命中次数。同一词表内长词优先，英文按词边界匹配，避免 `loss` 命中 `losses` 内部。
- `*_per_k`：命中次数 / 内容词数 × 1000
- `*_tfidf`：对词表中每个词，`tf = 次数 / 内容词数`，`idf = ln((N+1)/(df+1))+1`，再求和。`N` 和 `df` 来自本次成功解析、且非重复的章节样本
- `fog_index`：英文是 Gunning Fog，`0.4 × (词数/句数 + 100 × 三音节及以上词占比)`。中文是同结构的类比，`0.4 × (词数/句数 + 100 × 四字及以上词占比)`。`avg_sentence_len` 在中文样本里是每句汉字数
- `tone_net`：`(积极词数 - 消极词数) / 内容词数`。`risk` / `风险` 放在不确定词里，不进消极词。词典法不处理否定，`没有改善` 仍会计入 `改善`
- `yoy_similarity`：同一市场、同一公司、同一章节、上一会计年度的 TF-IDF 余弦（去掉停用词）。没有上一年则为空
- `disclosure_drift`：`1 - yoy_similarity`

重复的公司-章节-年份保留正文字数更长的一条参与 TF-IDF 和同比，另一条 `is_duplicate=1`。

词表在 `src/filingtext/lexicons/`。改完重新跑批处理即可，看板侧栏的临时词只影响当次高亮。

## 测试

```powershell
pytest
```
