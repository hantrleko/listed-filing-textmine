"""合成年报，只用于打通管线，不是真实披露。

正文按行业来写，并且足够长，避免几十个词把每千词强度放大一个数量级。
主题词只出现在各年单独的那一段里，用来看出年份之间的差别。
"""

from __future__ import annotations

_BANK_SHARED = """
报告期内，公司营业收入保持增长，利息净收入和手续费仍是利润的主要来源。
公司吸收的客户资金以结算存款和一年以内的个人储蓄为主，对公活期存款服务日常收付。
零售条线以储蓄账户、借记卡和代发工资为主，网点负责开户、挂失和存单支取。
对公条线为制造业和批发客户办理流动资金贷款、银行承兑汇票和国内信用证。
定价上，新发放贷款利率跟随贷款市场报价利率调整，存量房贷按合同约定重定价。
手续费来自银行卡、结算和托管，理财产品只代销，不在表内占款。
资产质量按五级分类管理，不良贷款率、关注类贷款占比和拨备覆盖率按季报送董事会。
资本方面，核心一级资本充足率、一级资本充足率和资本充足率都高于监管最低要求，并保留缓冲。
流动性上，流动性覆盖率和净稳定资金比例按日监测，合格优质资产以国债和政策性金融债为主。
同业业务以拆借和买入返售为主，期限短，对手方限于银行和清算机构。
票据业务服务企业支付，贴现利率随货币市场利率变动，不做以票养票的空转。
普惠小微贷款单户额度控制在监管口径以内，审批看流水、纳税和实际控制人征信。
信用卡透支计入个人贷款，分期手续费按摊余成本确认，逾期账户进入催收而不是核销了事。
理财子公司的产品单独核算，母行不承诺保本，代销时向客户说明净值波动。
金融投资以利率债和高等级信用债为主，交易账户和银行账户分开计价。
内部资金转移定价按期限和币种拆给业务条线，用来比较存贷司库的贡献。
审计委员会按季听取预期信用损失模型的参数，宏观经济情景只用于拨备，不写成市场预测。
对公客户的日常结算通过网银和柜台完成，代发、代扣和现金归集按协议收费。
个人住房按揭以抵押为主，提前还款按合同约定处理，还款计划与工资流水对照。
银行卡收单覆盖超市和餐饮商户，手续费按交易金额的约定比例收取，退货单独冲回。
债券投资分成持有和交易两类记账，久期控制在董事会批准的限额以内，不追逐波段。
汇率敞口以美元和欧元为主，用远期结汇对冲进口付汇，不对客户承诺汇率点位。
操作差错按等级报送，案件损失进入营业外支出，不混进利息支出。
合规部门审查新产品的合同文本和宣传材料，销售人员只按说明书介绍产品。
分支机构的信贷审批权限按金额分级，超限业务报到总行授信委员会。
内部审计按年覆盖信贷和财会，发现问题限期整改，并在下一次审计里回头看。
同业存单用于补充负债，期限以一年以内为主，发行利率随市场利率变动。
存款保险按监管口径缴纳，保费进入业务及管理费，不向储户另外收取。
大额存单面向个人和对公客户，起点金额和期限按产品说明书执行。
贷款承诺和保函在表外披露，客户实际用款之后才进入贷款余额。
集团客户统一授信，成员企业的用信占用集团额度，防止同一控制人多头融资。
关联交易按商业原则定价，并提交董事会审议，不通过关联方调节利润。
利润分配由董事会提出预案，提交股东大会，现金分红来自当年可供分配利润。
已发行的二级资本债计入二级资本，不计入核心一级资本，到期前提前赎回要另行审批。
流动性缺口按季做压力情景，结果向高级管理层报告，不在年报里写预测数字。
客户投诉按渠道登记，十五个工作日内答复，重复投诉单独统计。
反洗钱监测覆盖大额和可疑交易，报告报送监管机构，年报不列客户名单。
员工行为管理禁止代客操作和飞单，积分与绩效挂钩，检查记录留存备查。
押运和凭证打印外包给持牌机构，责任边界写进合同，空白凭证由支行双人保管。
网点只更新柜台和自助机具，装修费用按费用核算，不资本化到长期资产。
托管业务为基金和理财产品保管资产，按规模收托管费，不承担投资盈亏。
债券承销收入是手续费，余额包销的部分单独限额，不长期占用自有资金。
票据贴现占用信贷额度，贸易背景按发票和合同抽查，贴现利息按实际天数计算。
普惠贷款可以由担保公司分担一部分，银行保留审批权，担保范围写进协议。
信用卡分期的核销与继续追索分开列示，核销不是放弃债权。
外汇存款和结售汇分开统计，个人结汇按便利化额度办理，超限额的要提供用途。
机构客户的现金管理包括收付款归集和余额通知，通知只发给客户自己。
银团贷款由牵头行和参加行按份额承担，收费包括安排费和承诺费。
并购贷款看还款来源和抵押物，期限与项目现金流匹配，不把过桥资金做成项目贷款。
小微续贷看上一期的还本付息记录和纳税，不因为同一客户就自动放款。
同业投资只做利率债和高等级信用债的回购，对手方准入名单按季更新。
财务公司账户纳入集团资金归集，日终余额回到总行清算，不在财务公司沉淀。
银行卡盗刷损失按协议和责任认定分担，客户挂失之前的损失单独登记。
按揭抵押物每年抽查权证，权证原件入库，释放抵押要客户结清贷款。
信用证开证占用贸易融资额度，到单之后付款或承兑，不符点按国际惯例处理。
保函的保证金比例按客户评级确定，见索即付保函单独审批。
内部资金价格按月重定，条线利润要扣除资金成本和拨备，再看是否覆盖费用。
董事会风险管理委员会听取消贷、市场和操作三类报告，会议纪要归档。
监管评级和监管意见在年报里说明落实情况，整改事项列明负责部门和期限。
""".strip()

_MAKER_SHARED = """
报告期内，公司订单保持增长，家电零部件和小型电机仍是主业。
客户是国内整机厂，订单以季度框架合同加上月度排产，临时插单单独核价。
主要产线在两个工厂，冲压、注塑、绕线和总装分开核算，产能按双班口径统计，不把外协算进自有产能。
原材料以铜、铝和工程塑料为主，采购按季度招标，库存按订单覆盖周数管理。
出货以国内物流为主，出口用海运，交货期写进合同，延期按日扣款。
成本里直接材料占比最高，人工和制造费用按工时分摊到型号。
毛利随铜价和开工率变动，公司用套保锁定一部分铜价，不把套保盈亏说成主业。
质量部门按批次抽检尺寸和绝缘，退货单独记账，不并进正常销量。
销售按整机厂的排产计划发货，渠道库存由客户掌握，公司不压货。
资本开支用于模具和检测设备，折旧按直线法，在建工程转固后才计提。
研发费用化处理，课题围绕电机效率和噪音，形成的专利归公司所有。
应收款按客户账期管理，逾期单独列示，不把票据贴现做成隐藏借款。
员工以生产工人和工艺工程师为主，工资按产量和合格率考核。
模具按寿命和冲次摊销，达到次数后报废，不把未使用的模具提前转费用。
铜铝按月询价，合格供应商不少于三家，单一供应商的采购占比设上限。
成品按客户和型号分库，先进先出，呆滞超过九十天的单独计提。
来料不良退回供应商，索赔与货款对冲，不进销售收入。
总装按工单领料，盘点差异当月处理，不允许以盘盈抵下月短料。
出厂检验记录随批次保存，客户抽检不合格的整批隔离。
运输保险按货值投保，途中损失找承运人，不改写发货数量。
出口报关按合同和发票，收汇核销与订单号对应，不把预收写成销售收入。
售后只换同型号零件，换下的旧件入库，维修收入单独列示。
认证费用按证书有效期摊销，新客户的样品费进入销售费用。
电费和模具维修进入制造费用，不混进直接材料。
夜班和加班工资按产量计件之外另计，社保按工资基数缴纳。
设备点检由班组填写，停机时间按原因分类，计划保养不计入故障。
客户对账按月完成，差异超过阈值的暂停发货，直到双方确认。
废料按金属和塑料分开出售，收入冲减材料成本，不进其他业务收入。
外协只做表面处理和部分注塑，图纸和模具仍归公司，外协厂不得留样。
新模具的试模费用进研发或制造费用，试模件不入库销售。
报价单列材料、加工和运费，铜价联动条款按公开牌价结算差额。
安全库存只覆盖两周主料，不为了开工率提前大量采购。
车间按型号切换要清线，剩余零件退库，避免混料。
质检抽检比例按客户等级和上月合格率调整，加严抽检的批次单独标记。
出货前核对订单、箱单和合格证，三单不一致的不得装车。
厂房租赁按合同年限摊销，租赁改良在剩余租期内折旧。
银行承兑贴现要经过财务负责人审批，贴现息进财务费用。
所得税按利润总额调整研发加计后计提，不把递延项目写成现金。
董事会按季看订单、毛利和应收周转，经营讨论只写已经发生的产销。
注塑件按颜色和牌号分开存放，换色前要清机，清机料不入库。
绕线的漆包线按批次领用，线径用卡尺复核，不合格线轴退回仓库。
总装工单写明用料定额，超领要班组长签字，月末把超领和工废对上。
包装按客户图号，纸箱和泡沫计入包装物，不摊进零件单价。
客户驻厂检验的时间记入交付周期，不合格项当天关闭或隔离。
备件库与成品库分开，维修领用备件不冲减当月销量。
进口零件的运费和报关费进入采购成本，付款按提单和发票匹配。
""".strip()

_US_SHARED = """
We design and assemble handheld instruments for hospitals and equipment makers in the United States and Canada. A customer order is booked when the purchase order arrives, and we ship finished units from one warehouse in Ohio. Revenue is recognized when control of the instrument passes to the customer. Component cost and assembly hours determine gross margin. Receivables follow the stated terms on the invoice. Inventory is stored by model and lot, and payables follow supplier terms. Capital expenditure was limited to test benches and fixtures. Research spending remained in the income statement. The sales team covers existing accounts and does not run a separate online marketplace. We do not give earnings guidance in this section. Warranty returns are tracked by lot and are not added back to units shipped. Copper wire and plastic resin are the main inputs, and we buy them under quarterly agreements. Two shifts run the assembly line. Overtime is paid when a customer pulls an order forward. Quality checks cover size and insulation before a lot can leave the building. Scrap is sold by material type, and the proceeds reduce material cost. Customer deposits stay a liability until shipment. Bank fees and interest on the credit line are recorded in interest expense. The audit committee reviews the allowance for doubtful accounts each quarter. Plant lease payments are recorded as rent. Tooling is depreciated on a straight line, and routine repairs stay in expense. Packing follows the customer drawing. A lot that does not pass the outgoing check is quarantined. We match the bill of lading to the invoice before paying a carrier. Service parts are kept apart from finished instruments. Sample builds for a new account are expensed. The board reviews orders, margin, and receivable turnover each quarter, and this section describes activity that has already occurred.
""".strip()


def _cn_filing(company: str, year: int, shared: str, specific: str, closing: str) -> str:
    return f"""{company}{year}年年度报告

目录
第三节 管理层讨论与分析 .......... 3
第四节 公司治理 .......... 12

第三节 管理层讨论与分析
{shared}
{specific}
社会责任
公司在本节补充说明了经营讨论中的管理进展，该句应仍留在管理层讨论中。

第四节 公司治理
报告期内公司治理结构保持稳定，董事会运作规范，本段不应进入管理层讨论。
{closing}
"""


SAMPLE_DOCS = [
    {
        "filename": "000001_2022_annual.txt",
        "market": "CN",
        "ticker": "000001",
        "firm_name": "示例银行股份有限公司",
        "fiscal_year": 2022,
        "report_type": "annual",
        "text": _cn_filing(
            "示例银行股份有限公司",
            2022,
            _BANK_SHARED,
            "本年对符合条件的项目发放绿色信贷，并在年报中单列余额。核心系统仍使用原有信息系统，没有上线新的客户经营平台。出口业务的客户询问过关税变化，公司只做了结算提示。",
            "",
        ),
    },
    {
        "filename": "000001_2023_annual.txt",
        "market": "CN",
        "ticker": "000001",
        "firm_name": "示例银行股份有限公司",
        "fiscal_year": 2023,
        "report_type": "annual",
        "text": _cn_filing(
            "示例银行股份有限公司",
            2023,
            _BANK_SHARED,
            "绿色信贷余额继续单列，公司把碳达峰目标写进信贷政策，高耗能行业新增融资要额外说明。零售和对公审批试点人工智能和智能风控，客户数据集中到数据治理平台，这项工作称为数字化转型。出口管制使个别制造客户的订单推迟，公司收紧了与这些客户相关的贸易融资额度。",
            "",
        ),
    },
    {
        "filename": "000001_2024_annual.txt",
        "market": "CN",
        "ticker": "000001",
        "firm_name": "示例银行股份有限公司",
        "fiscal_year": 2024,
        "report_type": "annual",
        "text": _cn_filing(
            "示例银行股份有限公司",
            2024,
            _BANK_SHARED,
            "绿色信贷仍单列，但部分项目投放放缓。人工智能问答和大模型试运行延期，没有形成手续费收入，短期也没有改善网点效率。出口管制延续，相关客户的贸易融资余额下降，拨备随之增加，董事会认为挑战加大。",
            "",
        ),
    },
    {
        "filename": "600001_2022_annual.txt",
        "market": "CN",
        "ticker": "600001",
        "firm_name": "示例制造股份有限公司",
        "fiscal_year": 2022,
        "report_type": "annual",
        "text": f"""示例制造股份有限公司2022年年度报告

第三节 管理层讨论与分析
{_MAKER_SHARED}
生产环节完成自动化改造，车间的排产还靠人工台账。公司推进节能减排，单位产品电耗略降。关税调整对出口电机形成扰动，管理层开始关注地缘政治。

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
        "text": f"""示例制造股份有限公司2023年年度报告

第三节 管理层讨论与分析
{_MAKER_SHARED}
绕线车间在自动化之外试点人工智能、机器学习和工业互联网，并建设数据中台推进数字化转型。公司推进清洁生产、节能减排和绿色转型，开始核算温室气体排放强度。出口管制与关税并存，供应链中断使交付承压，地缘政治影响上升。

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
        "text": f"""UNITED STATES
SECURITIES AND EXCHANGE COMMISSION
Form 10-K
For the fiscal year ended December 31, 2022
NORTHWIND DEVICES INC.

TABLE OF CONTENTS
ITEM 1A. RISK FACTORS  3
ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS  5
ITEM 8. FINANCIAL STATEMENTS  9

ITEM 1A. RISK FACTORS
We face geopolitical risk. Tariffs, sanctions, and export controls may disrupt suppliers. A trade war or regional conflict could increase costs. These risk factors are specific to the risk section and should not be read as a forecast of revenue.

ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS
{_US_SHARED}
Revenue increased and profitability improved. Results were strong, and operating efficiency supported earnings growth. We continued a limited digital transformation and maintained our information system for order entry. Climate-related compliance costs were stable and were recorded in operating expense. The company reported no material impairment.

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
        "text": f"""UNITED STATES
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
{_US_SHARED}
Revenue increased, but an inventory impairment and a demand disruption weakened results. Profitability improved in the service segment, while the hardware segment reported a loss. We invested in artificial intelligence, machine learning, and cloud computing as part of a broader digital transformation. Climate risk and greenhouse gas compliance costs rose. Customers in two export markets delayed orders. Geopolitical risk is discussed under risk factors and is not repeated here as a performance claim.

ITEM 8. FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA
The consolidated balance sheet is omitted from this synthetic filing and must not enter the MD&A.
""",
    },
]
