# CGH 人力与运营数据可得性核查

核查日期：2026-09-20。问题：是否能取得足够资料，验证 CGH 在 2024-05-02 至 05-08 入院等待升高是否与人力配置有关。

## 已找到的院级原始资料

通过 [SingHealth 官方年报目录](https://www.singhealth.com.sg/about-singhealth/news/impact-reports)，取得 [FY2024/2025 Facts & Figures 原始 PDF](https://www.singhealth.com.sg/content/dam/singhealth-web/singhealth/about-singhealth/news/impact-reports/SH-Overview-24-25-FactsandFigures.pdf)。已下载完整文件并将第 3 页渲染核对：该页下部为 CGH，蓝色为截至 2025-03-31 年度，灰色为截至 2024-03-31 年度。未只依赖 PDF 文本抽取顺序。

原件：SingHealth_FY2024-2025_FactsAndFigures.pdf（版权归 SingHealth，未随仓库发布，可从上方官方链接下载）。文件大小 1,605,659 字节；SHA256：`fee3c4f6405bc6d237eaac9269718112c969c338cbf110796ef5ab3b8e739333`。

| CGH 指标（沿用原表分类） | Year ended 31 Mar 2024 | Year ended 31 Mar 2025 |
|---|---:|---:|
| Medical 人员 | 822 | 870 |
| Nursing 护理人员 | 2656 | 3129 |
| Beds 床位 | 1086 | 1132 |
| Accident & Emergency Attendances 年度急诊就诊量 | 131192 | 136630 |
| Average Length of Stay 平均住院日（天） | 6.8 | 6.7 |

这些数值可以补充医院规模和年度运营背景，但不能还原 2024 年 5 月那一周的实际在岗工时、病区配置或工作量。原表没有提供这些人员字段的班次细分；不得自行把它们解释成某日值、急诊专属人数或 FTE。两个年度也不是 2024、2025 两个自然年，目标周在截至 2025-03-31 的年度内，不能将两个年度总量的变化当成目标周与前一周的变化。

平均住院日属于住院停留指标，不是入院前等待时间。年度床位数的口径尚未与 MOH 每日 BOR 分母核实一致，不能用它倒推目标日可用空床数。年度全部住院量也不能当成急诊转住院人数，不能除以急诊总量计算急诊入院率。

额外质量提示：该页截至 2024-03-31 的各人员类别相加为 6393，但原表 Total Number 写为 6396，相差 3；原文件如此，原因未核实。本次保留原件，未擅自修正，也未将总人数纳入上表或据此计算比例。

## 仍缺什么，以及为什么缺它就不能确认人力瓶颈

本次定向检索覆盖 CGH、SingHealth、MOH、data.gov.sg，并核查相关官方年报、统计及业务流程页面。以下“未找到”仅限本次公开检索，不表示医院内部不存在资料。

| 所需资料 | 本次找到的公开粒度 | 验证目标周仍缺少的内容 |
|---|---|---|
| 医疗、护理及相关岗位供给 | 院级年度人员分类数量 | 按日期、班次和病区的实际在岗人数、有效工时、缺勤和技能配置 |
| 急诊入院需求 | 已有院级每日全部急诊就诊量 | 同期决定收治住院人数、实际转入病房人数、所需病区及床类 |
| 病例构成与护理工作量 | 全国疾病背景、医院一般就诊说明 | CGH 同期诊断、分诊等级、护理依赖程度等汇总分组 |
| 可接收床位 | 年度床位数、每日全院午夜 BOR | 各病区各班次可开放/可接收床位、关闭床位及原因 |
| 等待发生的具体环节 | 已有每日总等待 P50 | 配床、床位准备、交接、转运等分段时长及样本数 |

公开院级日表来源：[MOH 急诊量](https://www.moh.gov.sg/others/resources-and-statistics/healthcare-institution-statistics-attendances-at-emergency-medicine-departments/)、[MOH BOR](https://www.moh.gov.sg/others/resources-and-statistics/healthcare-institution-statistics-beds-occupancy-rate-%28bor%29/)、[MOH 等待时间](https://www.moh.gov.sg/others/resources-and-statistics/healthcare-institution-statistics-waiting-time-for-admission-to-ward/)。人员统计可对照 [MOH 全国年度 Health Manpower](https://www.moh.gov.sg/others/resources-and-statistics/health-manpower/)，但全国总量不能分配成 CGH 人数。

CGH 的[床位管理流程介绍](https://www.cgh.com.sg/about-cgh/overview/cgh90thanniversary/care-grows-here/ensuring-24-7-care-together)说明，BMU 会协调各病区释放床位、转移患者，并与急诊及病区临床团队共同安排转床。这使我们明确应该调查哪些环节和团队，但该介绍不是目标周的流程记录。

另有 [CGH 急诊机器人改善项目](https://child.chi.sg/learn/child-collection/projects/robots-to-augment-the-care-team-at-the-emergency-department-ed/)描述通过导引、送毯与送药减少重复任务。它可作为运营改善措施的案例，不能代替目标周的人员数据，不能把其他项目报告的效果写成本个人项目成果。

## 拟向院方申请的最小数据范围

优先申请 2024-04-01 至 06-30 的汇总数据，使目标周有前后对照；这是拟议范围，尚未获得。优先使用日期＋班次＋科室/接收病区，并明确跨班次等待的归属规则。不需要员工姓名、患者身份、完整病历或个人排班明细。

1. 供给：急诊和接收病区按岗位的计划/实际在岗人数及有效临床工时；缺勤工时；可接收床位及暂时关闭原因。
2. 需求：急诊就诊量、决定住院人数、实际转入病房人数，以及诊断/分诊等级/所需病区等适当分组。
3. 流程：决定收治至床位分配、床位分配至准备完成、准备完成至离开急诊的分段等待统计与各段有效样本数。各段 P50 不能直接相加当作总等待 P50。
4. 口径：班次起止、人员是否按人数或 FTE 统计、有效工时定义、床位类型、缺失标识、时间归属及期间流程调整说明。

如果无法提供班次汇总，可先问是否提供日度或周度汇总，并相应收窄结论。仅有年度值时，不插值制造每日排班，也不将年度总人数平均分摊后当成实际在岗人数。

以下为最初拟议的英文询问稿。后续经学习者同意，已于 2026-09-20 16:50 从其学校邮箱发至 CGH 官方公众咨询邮箱（发送记录含个人联系方式，未随仓库公开）。下方保留初稿供追溯：

> Subject: Availability of aggregate staffing and admission-flow data for a personal healthcare analytics project
>
> Dear CGH team,
>
> I am working on a personal healthcare analytics project using MOH's published daily emergency department attendances, bed occupancy rates and median admission waiting times. I am investigating an increase in CGH's admission waiting times during 2–8 May 2024, without presuming that staffing was the cause.
>
> Could you advise whether any public dataset or shareable aggregate information is available for 1 April–30 June 2024 on: (1) planned and actual staffing or clinical staff-hours by day/shift for the ED and receiving wards; (2) patients with a decision to admit from the ED and completed ward transfers; (3) available staffed beds by ward type; and (4) aggregate time intervals for bed allocation, bed readiness and departure from the ED?
>
> If shift-level information is unavailable, daily or weekly aggregates, published studies, or guidance on the appropriate data request process would also be helpful. Please include relevant definitions and coverage limitations where available. No patient-identifiable information or individual employee rosters are requested.
>
> Thank you for your guidance.

## 拿到数据后怎样判断

先检查等待增加发生在哪段流程，再看该段需求与实际人员供给的关系；在可比星期、时段和病例构成下扩展比较。繁忙时段可能临时增派人员，因此“人员更多但等待也长”的相关性不能直接证明增派无效。即使存在人力与等待关联，也仍需区分持续缺人、排班错配和其他限制，才能提出招聘或排班试点建议。

目前完成的成果是：获得并核对真实院级年度资料，明确公开数据缺口，形成具体申请字段，并于 2026-09-20 16:50 完成 CGH 咨询邮件发送。尚未验证人员瓶颈，未提出确定招聘人数，未声称院方会提供数据或已同意合作。
