# BEHAVIOR 网站资源与机器人型号调研

本项目通过网页抓取、公共学术索引检索和人工证据核验，整理
[BEHAVIOR](https://behavior.stanford.edu/) 网站可以提供的资源、网站支持或提及的机器人与
机械臂型号，以及官网贡献者在机器人论文中实际使用的设备型号。

项目只读取公开页面，不访问登录或受限内容。学术索引仅用于发现候选论文，不直接作为机器人
型号证据。

## 当前完成情况

截至 2026-07-02，已经完成：

1. **网站资源清单**
   - 整理了 15 项资源。
   - 覆盖 BEHAVIOR-1K、BEHAVIOR-100、OmniGibson、BDDL、Knowledgebase、3D 场景与
     物体资产、Challenge 数据、遥操作、评测、论文和代码仓库等入口。

2. **网站机器人与机械臂清单**
   - 从 OmniGibson Robots 文档及官网项目页整理了 14 个条目。
   - 包括 TurtleBot 2、LoCoBot、Husky、Freight、Franka Research 3、ViperX 300、
     Fetch、TIAGo、Stretch、Galaxea R1/R1 Pro 等。
   - 分开记录整机类别、厂商、机械臂、自由度和末端执行器，避免混淆整机与机械臂。

3. **官网贡献者名册**
   - 从官网提取了 57 位贡献者：Core Team 15、Supporting Team 11、Alumni 31。
   - 覆盖 Core Team、Supporting Team 和 Alumni，并保留个人主页。

4. **贡献者论文与机器人型号**
   - 论文时间范围固定为 2022-01-01 至 2026-07-01。
   - 通过 Crossref 为贡献者发现并去重了 70 条待全文核验的“贡献者—论文”候选记录。
   - 已形成 32 条具有明确证据的“贡献者—论文—型号”记录，涉及 13 位贡献者和 2 篇
     已核验论文。
   - 当前已核验型号包括 Galaxea R1 和 PAL Robotics TIAGo（双臂配置）。
   - 已确认属于机器人研究、但没有公开具体型号的论文单独保存，不参与型号排名。

5. **型号统计**
   - 主排名采用“贡献者—论文—型号”记录数。
   - 同时提供不同贡献者数和不同论文数。
   - 整机、机械臂、末端执行器分别统计。
   - 当前已核验记录中，Galaxea R1 有 20 条记录，涉及 13 位贡献者和 2 篇论文；
     TIAGo（双臂配置）有 12 条记录，涉及 12 位贡献者和 1 篇论文。

6. **可重复运行与测试**
   - 已配置独立 Conda 环境 `behavior-data`。
   - 实现同域、单线程、限速并检查 `robots.txt` 的网页读取器。
   - 实现贡献者解析、学术候选发现、型号别名归一化、论文去重、时间过滤和统计生成。
   - 当前共有 19 项自动化测试。

## 结果文件

主要结果位于 `reports/`：

| 文件 | 内容 |
| --- | --- |
| `report.md` | 中文汇总报告，包含三个主要 List 和型号统计 |
| `resources.csv` | List 1：网站资源 |
| `website_robot_models.csv` | List 2：网站机器人、机械臂和末端执行器 |
| `contributor_paper_robots.csv` | List 3：经过型号证据核验的贡献者论文 |
| `robot_model_statistics.csv` | 整机、机械臂和末端执行器的分层统计 |
| `robot_prices.csv` | 14 个官网机器人条目的公开价格、询价/停产状态、人民币参考价和证据 |
| `contributors.csv` | 官网贡献者、分组和个人主页 |
| `paper_candidates.csv` | 学术索引发现、等待全文核验的论文候选 |
| `unresolved_paper_models.csv` | 已确认机器人研究但具体型号未披露的记录 |
| `link_validation.csv` | 正式资源和证据链接的联网验证结果 |
| `report_audit.csv` | 从上游 CSV 独立重算报告数量、排名、价格、图片和链接的审计结果 |

`list_1_resources.csv`、`list_2_site_robots.csv` 和
`list_3_contributor_paper_robots.csv` 是三个主 List 的兼容命名副本。

原始和中间数据位于 `data/`：

- `data/catalog.json`：经过核验的资源、机器人和论文型号证据目录。
- `data/price_catalog.json`：价格快照、原币报价、汇率及来源；数值不会从相似型号反推。
- `reports/assets/robots/`：从 BEHAVIOR 官网机器人页保存的 14 张型号图片，报告中紧邻型号展示。
- `data/contributors.json`：官网贡献者名册。
- `data/crossref_candidates.json`：Crossref 原始候选结果。
- `data/raw/`：抓取页面及断点状态。

## 环境搭建

项目使用 Conda。首次创建环境：

```powershell
conda env create -f environment.yml
conda activate behavior-data
```

环境已经存在时：

```powershell
conda env update -f environment.yml --prune
conda activate behavior-data
```

确认环境：

```powershell
python --version
python -m pytest --basetemp .pytest_tmp
```

当前验证版本为 Python 3.12，测试应显示 `19 passed`。

## 完整复现

### 1. 更新官网贡献者和论文候选

使用无需 API key 的 Crossref：

```powershell
conda activate behavior-data
python -m scripts.collect_research --discover-crossref
```

程序会：

1. 读取 BEHAVIOR 官网首页；
2. 更新 Core、Supporting、Alumni 名册；
3. 按贡献者检索 2022–2026 论文；
4. 使用作者姓名、时间窗和机器人关键词过滤候选；
5. 在 `data/raw/crossref_progress.json` 中保存断点。

如果请求中断，执行相同命令即可继续。

OpenAlex 匿名作者检索恢复可用，或具备相应 API 访问条件后，可以增补候选：

```powershell
python -m scripts.collect_research --discover-openalex
```

### 2. 核验论文型号

`paper_candidates.csv` 只是候选队列。型号必须在以下来源之一得到明确证明：

- 论文正文或补充材料；
- 论文官方项目页；
- 论文官方代码或实验配置。

只统计实验、数据采集、真实部署或仿真实验实际使用的设备。Related Work 中泛泛提到的
型号不计入。核验结果写入 `data/catalog.json`；无法确认型号时记录为“未披露”或
“自研平台”，不推断图片中的设备。

### 3. 重新生成全部报告

```powershell
python -m scripts.build_catalog
```

该命令会重新生成三个主 List、贡献者表、未决表、候选表、型号统计、价格表和中文报告。

### 4. 运行测试和一致性检查

```powershell
python -m pytest --basetemp .pytest_tmp
```

联网验证正式资源、论文和证据链接：

```powershell
python -m scripts.validate_report --strict
python -m scripts.audit_report
```

结果写入 `reports/link_validation.csv`；严格模式下出现 404 或网络错误会返回失败。

测试覆盖：

- 官网贡献者和分组解析；
- 个人主页提取；
- URL 与型号别名归一化；
- 2022–2026 时间过滤；
- 非官网贡献者排除；
- 作者—论文—型号记录去重；
- 整机、机械臂和末端执行器分层统计。
- 14 个机器人价格条目的完整覆盖、币种换算，以及询价/非商品记录不得生成虚构人民币价格。

价格数据是 `data/price_catalog.json` 中以查询日保存的快照。更新价格时应先核对销售型号、
代际、配置、整机/配件范围和税费状态，再运行生成与严格链接验证命令。人民币金额只作为
统一汇率日的参考，不含来源未明确的税、运费、关税或集成服务费。正式表不收录二手挂牌价；
停产型号只保留可追溯的历史新品价，找不到时明确写“无公开价格”。

## 单独使用网页读取器

读取少量公开页面：

```powershell
python -m behavior_reader --max-pages 5 --delay 1.5
```

从指定入口读取：

```powershell
python -m behavior_reader `
  --start-url https://behavior.stanford.edu/knowledgebase/ `
  --max-pages 20 `
  --delay 1.5
```

网页结果写入：

- `data/raw/pages.jsonl`：正文、链接和抓取时间；
- `data/processed/pages.csv`：页面级摘要。

## 数据口径与限制

- “全部贡献者”以抓取当日官网首页为准。
- “近五年”固定为 2022-01-01 至 2026-07-01。
- “论文全集”指公开渠道能够发现并核验的集合，不保证覆盖未索引、未公开或无法访问全文的论文。
- Crossref/OpenAlex 可能漏收论文或发生同名作者误匹配，因此候选必须再做个人主页、机构、
  共同作者和全文证据核验。
- 只有 `verification_status=verified` 且具有证据链接的具体型号进入排行榜。
- 统计主单位是一条“贡献者—论文—型号”记录；共同作者论文会为每位官网贡献者分别产生记录。
- 官网机器人文档正文称支持 12 种机器人，但当前页面实际呈现 14 个条目。本项目按页面条目
  记录，并保留 Franka Mounted 等配置变体。

## 合理使用边界

- 只读取无需登录即可访问的公开页面。
- 检查站点 `robots.txt`，不绕过访问限制。
- 网页抓取采用同域、单线程和请求间隔限制。
- 不自动下载大型图片、视频、压缩包或仿真数据集。
- 学术索引只用于论文发现，不把搜索结果自动当作实验事实。
