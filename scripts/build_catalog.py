from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import pandas as pd

from behavior_reader.pricing import (
    build_price_frame,
    format_cny_price,
    format_original_price,
)
from behavior_reader.research import expand_paper_records, model_statistics, normalize_name


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = DATA / "catalog.json"
CONTRIBUTORS = DATA / "contributors.json"
OPENALEX_CANDIDATES = DATA / "openalex_candidates.json"
CROSSREF_CANDIDATES = DATA / "crossref_candidates.json"
SITE_SNAPSHOT = DATA / "site_snapshot.json"
PRICE_CATALOG = DATA / "price_catalog.json"
OUTPUT = ROOT / "reports"

ROBOT_METADATA = {
    "TurtleBot 2 / Kobuki": ("Yujin Robot / Open Robotics", "", ""),
    "LoCoBot": ("Trossen Robotics / Interbotix", "LoCoBot arm (disabled)", ""),
    "Clearpath Husky": ("Clearpath Robotics", "", ""),
    "Fetch Robotics Freight": ("Fetch Robotics", "", ""),
    "Franka Research 3": ("Franka Robotics", "Franka Research 3", "parallel-jaw gripper"),
    "Trossen ViperX 300 6DOF": ("Trossen Robotics", "ViperX 300", "parallel-jaw gripper"),
    "A1": ("Galaxea Dynamics", "A1", "Inspire-Robots Dexterous Hand"),
    "Franka Research 3 mounted cart": (
        "Franka Robotics",
        "Franka Research 3",
        "parallel-jaw gripper",
    ),
    "Fetch": ("Fetch Robotics", "integrated 7-DoF Fetch arm", "parallel-jaw gripper"),
    "PAL Robotics TIAGo (dual-arm configuration)": (
        "PAL Robotics",
        "two integrated 7-DoF TIAGo arms",
        "two parallel-jaw grippers",
    ),
    "Hello Robot Stretch": ("Hello Robot", "integrated 5-DoF Stretch arm", "Stretch gripper"),
    "Galaxea R1": (
        "Galaxea Dynamics",
        "two integrated 6-DoF R1 arms",
        "two parallel-jaw grippers",
    ),
    "Galaxea R1 Pro": (
        "Galaxea Dynamics",
        "two integrated 7-DoF R1 Pro arms",
        "two parallel-jaw grippers",
    ),
    "BehaviorRobot": ("BEHAVIOR project", "two virtual arms", "two virtual grippers"),
}

ROBOT_MANUFACTURER_EVIDENCE = {
    "TurtleBot 2 / Kobuki": "https://www.turtlebot.com/turtlebot2/",
    "LoCoBot": "https://docs.trossenrobotics.com/interbotix_xslocobots_docs/",
    "Clearpath Husky": (
        "https://docs.clearpathrobotics.com/docs_robots/outdoor_robots/"
        "husky/a200/user_manual_husky"
    ),
    "Fetch Robotics Freight": "https://fetchrobotics.github.io/docs/",
    "Franka Research 3": "https://franka.de/franka-research-3-cobot-arm",
    "Trossen ViperX 300 6DOF": (
        "https://store.trossenrobotics.com/products/viperx-300-s-robot-arm"
    ),
    "A1": "https://www.robotsusa.com/Galaxea-A1-A1-Robotic-Arm.htm",
    "Franka Research 3 mounted cart": "https://franka.de/franka-research-3-cobot-arm",
    "Fetch": "https://fetchrobotics.github.io/docs/",
    "PAL Robotics TIAGo (dual-arm configuration)": "https://pal-robotics.com/robot/tiago/",
    "Hello Robot Stretch": "https://hello-robot.com/",
    "Galaxea R1": "https://arxiv.org/html/2503.05652",
    "Galaxea R1 Pro": (
        "https://galaxea-dynamics.com/products/"
        "galaxea-r1-pro-universal-humanoid-robot"
    ),
    "BehaviorRobot": "https://behavior.stanford.edu/omnigibson/robots.html",
}

ROBOT_IMAGE_FILES = {
    "TurtleBot 2 / Kobuki": "Turtlebot.png",
    "LoCoBot": "Locobot.png",
    "Clearpath Husky": "Husky.png",
    "Fetch Robotics Freight": "Freight.png",
    "Franka Research 3": "FrankaPanda.png",
    "Trossen ViperX 300 6DOF": "VX300S.png",
    "A1": "A1.png",
    "Franka Research 3 mounted cart": "FrankaMounted.png",
    "Fetch": "Fetch.png",
    "PAL Robotics TIAGo (dual-arm configuration)": "Tiago.png",
    "Hello Robot Stretch": "Stretch.png",
    "Galaxea R1": "R1.png",
    "Galaxea R1 Pro": "R1Pro.png",
    "BehaviorRobot": "BehaviorRobot.png",
}


def robot_image_html(model: str) -> str:
    filename = ROBOT_IMAGE_FILES.get(model, "")
    if not filename:
        return ""
    source = f"https://behavior.stanford.edu/assets/robots/{filename}"
    return (
        f'<a href="{source}"><img src="assets/robots/{filename}" '
        f'alt="{model}" width="120"></a>'
    )


def markdown_table(frame: pd.DataFrame, limit: int | None = None) -> str:
    if frame.empty:
        return "_无记录。_"
    values = frame.head(limit).fillna("").astype(str) if limit else frame.fillna("").astype(str)
    headers = list(values.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in values.itertuples(index=False, name=None):
        escaped = [value.replace("|", "\\|").replace("\n", " ") for value in row]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines)


def infer_year(paper: dict[str, Any]) -> int:
    if paper.get("year"):
        return int(paper["year"])
    match = re.search(r"arxiv\.org/abs/(\d{2})", paper.get("paper_url", ""))
    return 2000 + int(match.group(1)) if match else 0


def migrate_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    for paper in catalog["papers"]:
        paper.setdefault("year", infer_year(paper))
        arxiv_match = re.search(r"arxiv\.org/abs/([^/?#]+)", paper.get("paper_url", ""))
        paper.setdefault("arxiv_id", arxiv_match.group(1) if arxiv_match else "")
        paper.setdefault("doi", "")
        paper.setdefault(
            "verification_status",
            "partial" if not paper.get("models") else "verified",
        )
        for model in paper.get("models", []):
            model.setdefault("entity_type", "robot")
            model.setdefault("robot_type", model.pop("type", ""))
            if paper["title"].startswith("MoMaGen") and model["model"] == "Galaxea R1":
                model.setdefault("usage_context", "采集源演示并生成训练数据")
                model.setdefault("world", "real and simulation")
            elif paper["title"].startswith("MoMaGen") and model["model"].startswith(
                "PAL Robotics TIAGo"
            ):
                model.setdefault("usage_context", "跨本体轨迹生成")
                model.setdefault("world", "simulation")
            elif paper["title"].startswith("BEHAVIOR Robot Suite"):
                model.setdefault("usage_context", "真实家庭任务、数据采集与策略评测")
                model.setdefault("world", "real world and simulation ablation")
            else:
                model.setdefault("usage_context", "实验或数据生成")
                model.setdefault("world", "real/simulation")
            if model["model"] == "Galaxea R1":
                model.setdefault("end_effector", "parallel-jaw gripper")
            elif model["model"].startswith("PAL Robotics TIAGo"):
                model.setdefault("end_effector", "parallel-jaw gripper")
            else:
                model.setdefault("end_effector", "")
            model.setdefault("evidence_url", paper.get("project_url", paper["paper_url"]))
            model.setdefault("evidence_location", "official project page")
            model.setdefault("verification_status", "verified")
    return catalog


def website_robot_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    output: list[dict[str, Any]] = []
    for row in rows:
        manufacturer, arm, end_effector = ROBOT_METADATA.get(row["model"], ("", "", ""))
        output.append(
            {
                "site_name": row["site_name"],
                "model": row["model"],
                "image_path": f"assets/robots/{ROBOT_IMAGE_FILES[row['model']]}",
                "image_source_url": (
                    "https://behavior.stanford.edu/assets/robots/"
                    f"{ROBOT_IMAGE_FILES[row['model']]}"
                ),
                "category": row["type"],
                "manufacturer": manufacturer,
                "dof": row.get("dof", ""),
                "arm_model": arm or row.get("arm_model", ""),
                "end_effector": end_effector,
                "evidence_url": row["source"],
                "manufacturer_evidence_url": (
                    ROBOT_MANUFACTURER_EVIDENCE.get(row["model"], "")
                    if manufacturer
                    else ""
                ),
                "arm_evidence_url": row["source"] if (arm or row.get("arm_model")) else "",
                "end_effector_evidence_url": row["source"] if end_effector else "",
            }
        )
    return pd.DataFrame(output)


def load_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def usage_ranking(
    records: pd.DataFrame,
    robot_types: set[str],
    limit: int = 5,
) -> pd.DataFrame:
    subset = records[
        records["verification_status"].eq("verified")
        & records["robot_type"].isin(robot_types)
    ]
    if subset.empty:
        return pd.DataFrame(columns=["排名", "型号", "记录数", "贡献者数", "论文数"])
    ranking = (
        subset.groupby("model_canonical", as_index=False)
        .agg(
            记录数=("person", "size"),
            贡献者数=("person", "nunique"),
            论文数=("paper", "nunique"),
        )
        .rename(columns={"model_canonical": "型号"})
        .sort_values(
            ["记录数", "贡献者数", "论文数", "型号"],
            ascending=[False, False, False, True],
        )
        .head(limit)
        .reset_index(drop=True)
    )
    ranking.insert(0, "排名", range(1, len(ranking) + 1))
    return ranking


def deduplicate_candidates(
    rows: list[dict[str, Any]],
    verified: pd.DataFrame,
    contributors: list[dict[str, str]],
) -> pd.DataFrame:
    roster = {normalize_name(row["name"]): row for row in contributors}
    verified_pairs = {
        (normalize_name(row.person), re.sub(r"[^a-z0-9]+", "", row.paper.casefold()))
        for row in verified.itertuples()
    }
    seen: set[tuple[str, str]] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        roster_entry = roster.get(normalize_name(row["person"]))
        if roster_entry is None:
            continue
        key = (
            normalize_name(row["person"]),
            re.sub(r"[^a-z0-9]+", "", row["paper"].casefold()),
        )
        if key in seen or key in verified_pairs:
            continue
        seen.add(key)
        output.append(
            {
                "person": roster_entry["name"],
                "contributor_group": roster_entry["group"],
                "homepage": roster_entry["homepage"],
                "paper": row["paper"],
                "year": row["year"],
                "paper_url": row["paper_url"],
                "doi": row["doi"],
                "discovery_source": row.get("discovery_source", "OpenAlex"),
                "status": "candidate_needs_fulltext_verification",
                "topics": "; ".join(row.get("topics", [])),
            }
        )
    return pd.DataFrame(output)


def main() -> None:
    catalog = migrate_catalog(load_json(SOURCE, {}))
    contributors = load_json(CONTRIBUTORS, [])
    if not contributors:
        raise SystemExit("Missing data/contributors.json; run scripts/collect_research.py first")
    candidates = load_json(OPENALEX_CANDIDATES, []) + load_json(CROSSREF_CANDIDATES, [])
    snapshot = load_json(SITE_SNAPSHOT, {})
    price_catalog = load_json(PRICE_CATALOG, {})
    OUTPUT.mkdir(parents=True, exist_ok=True)

    resources = pd.DataFrame(catalog["resources"])
    challenge_name = snapshot.get("challenge_name", "BEHAVIOR Challenge")
    challenge_landing_name = snapshot.get(
        "challenge_landing_name", "BEHAVIOR Challenge landing page"
    )
    resources.loc[
        resources["name"].eq("BEHAVIOR Challenge Dataset"), "name"
    ] = f"{challenge_name} Dataset"
    resources.loc[
        resources["name"].eq("BEHAVIOR Challenge"), "name"
    ] = challenge_landing_name
    if challenge_landing_name != challenge_name:
        resources.loc[
            resources["name"].eq(challenge_landing_name), "description"
        ] = (
            "Challenge landing page; its page title is "
            f"{challenge_landing_name}, while the homepage advertises {challenge_name}."
        )
        challenge_version_note = (
            f"注意：抓取日官网首页和 Dataset 页面显示 {challenge_name}，但 "
            f"`/challenge/` 落地页显示 {challenge_landing_name}。本报告保留这一官网"
            "自身的版本差异，不把落地页内容误标成同一年。"
        )
    else:
        challenge_version_note = (
            f"Challenge 年份已分别从首页和落地页提取，两处当前均为 {challenge_name}。"
        )
    robots = website_robot_frame(catalog["robots"])
    robot_report_display = robots.copy()
    robot_report_display.insert(
        2, "图片", robot_report_display["model"].map(robot_image_html)
    )
    papers, unresolved = expand_paper_records(catalog["papers"], contributors)
    stats = model_statistics(papers)
    candidate_frame = deduplicate_candidates(candidates, papers, contributors)
    contributor_frame = pd.DataFrame(contributors)
    prices = build_price_frame(price_catalog)
    category_by_model = robots.set_index("model")["category"].to_dict()
    prices["category"] = prices["behavior_model"].map(category_by_model)
    price_display = prices.copy()
    price_display["图片"] = price_display["behavior_model"].map(robot_image_html)
    price_display["原币价格"] = price_display.apply(format_original_price, axis=1)
    price_display["人民币参考"] = price_display.apply(format_cny_price, axis=1)
    price_display = price_display.rename(
        columns={
            "behavior_model": "BEHAVIOR型号",
            "sold_model": "销售型号或配置",
            "match_type": "匹配关系",
            "condition": "价格性质",
            "availability": "供应状态",
            "seller": "来源",
            "source_url": "价格链接",
            "confidence": "可信度",
            "notes": "说明",
        }
    )[
        [
            "BEHAVIOR型号",
            "图片",
            "销售型号或配置",
            "匹配关系",
            "价格性质",
            "供应状态",
            "原币价格",
            "人民币参考",
            "来源",
            "可信度",
            "价格链接",
            "说明",
        ]
    ]
    mobile_price_display = price_display.loc[
        prices["category"].eq("mobile robot")
    ].reset_index(drop=True)
    stationary_arm_price_display = price_display.loc[
        prices["category"].eq("stationary manipulator")
    ].reset_index(drop=True)
    mobile_manipulator_price_display = price_display.loc[
        prices["category"].isin(
            {"mobile manipulator", "bimanual mobile manipulator"}
        )
    ].reset_index(drop=True)
    noncommercial_price_display = price_display.loc[
        prices["category"].eq("VR bimanual agent proxy")
    ].reset_index(drop=True)
    numeric_new = prices[
        prices["price_kind"].isin({"fixed", "from", "range"})
        & prices["condition"].isin({"new"})
        & prices["confidence"].isin({"high", "medium"})
        & prices["cny_min"].notna()
    ]
    price_category_rows: list[dict[str, Any]] = []
    category_labels = {
        "mobile robot": "纯轮式移动机器人",
        "stationary manipulator": "固定机械臂",
        "mobile manipulator": "轮式机械臂机器人",
        "bimanual mobile manipulator": "轮式机械臂机器人",
    }
    for label in ("纯轮式移动机器人", "固定机械臂", "轮式机械臂机器人"):
        source_categories = {
            key for key, value in category_labels.items() if value == label
        }
        subset = numeric_new[numeric_new["category"].isin(source_categories)]
        price_category_rows.append(
            {
                "类别": label,
                "具有公开数字新品参考的报价数": len(subset),
                "最低人民币参考": (
                    f"¥{subset['cny_min'].min():,.0f}" if not subset.empty else "无"
                ),
                "最高人民币参考": (
                    f"¥{subset['cny_max'].max():,.0f}" if not subset.empty else "无"
                ),
            }
        )
    price_category_summary = pd.DataFrame(price_category_rows)
    site_type_summary = pd.DataFrame(
        [
            {
                "类型": "纯轮式移动机器人",
                "数量": int(robots["category"].eq("mobile robot").sum()),
                "型号": "、".join(
                    robots.loc[robots["category"].eq("mobile robot"), "model"]
                ),
            },
            {
                "类型": "固定机械臂",
                "数量": int(robots["category"].eq("stationary manipulator").sum()),
                "型号": "、".join(
                    robots.loc[
                        robots["category"].eq("stationary manipulator"), "model"
                    ]
                ),
            },
            {
                "类型": "轮式机械臂机器人",
                "数量": int(
                    robots["category"]
                    .isin({"mobile manipulator", "bimanual mobile manipulator"})
                    .sum()
                ),
                "型号": "、".join(
                    robots.loc[
                        robots["category"].isin(
                            {"mobile manipulator", "bimanual mobile manipulator"}
                        ),
                        "model",
                    ]
                ),
            },
            {
                "类型": "VR 双臂代理",
                "数量": int(robots["category"].eq("VR bimanual agent proxy").sum()),
                "型号": "、".join(
                    robots.loc[
                        robots["category"].eq("VR bimanual agent proxy"), "model"
                    ]
                ),
            },
        ]
    )
    mobile_ranking = usage_ranking(papers, {"mobile robot"})
    mobile_site_models = (
        robots.loc[
            robots["category"].eq("mobile robot"),
            ["model", "manufacturer", "arm_model", "evidence_url"],
        ]
        .rename(
            columns={
                "model": "官网型号",
                "manufacturer": "厂商",
                "arm_model": "机械臂状态",
                "evidence_url": "官网证据",
            }
        )
        .reset_index(drop=True)
    )
    mobile_site_models.insert(
        1, "图片", mobile_site_models["官网型号"].map(robot_image_html)
    )
    mobile_manipulator_ranking = usage_ranking(
        papers,
        {"mobile manipulator", "bimanual mobile manipulator"},
    )
    arm_ranking = (
        stats[stats["entity_type"].eq("arm")]
        .head(5)
        .rename(
            columns={
                "rank_within_type": "排名",
                "model": "型号",
                "record_count": "记录数",
                "unique_people": "贡献者数",
                "unique_papers": "论文数",
            }
        )[["排名", "型号", "记录数", "贡献者数", "论文数"]]
    )

    named_outputs = {
        "resources.csv": resources,
        "website_robot_models.csv": robots,
        "contributors.csv": contributor_frame,
        "contributor_paper_robots.csv": papers,
        "unresolved_paper_models.csv": unresolved,
        "paper_candidates.csv": candidate_frame,
        "robot_model_statistics.csv": stats,
        "robot_prices.csv": prices,
    }
    for name, frame in named_outputs.items():
        frame.to_csv(OUTPUT / name, index=False, encoding="utf-8-sig")

    # Compatibility aliases for the original three-list naming.
    resources.to_csv(OUTPUT / "list_1_resources.csv", index=False, encoding="utf-8-sig")
    robots.to_csv(OUTPUT / "list_2_site_robots.csv", index=False, encoding="utf-8-sig")
    papers.to_csv(
        OUTPUT / "list_3_contributor_paper_robots.csv",
        index=False,
        encoding="utf-8-sig",
    )
    unresolved.to_csv(
        OUTPUT / "list_3_unresolved_papers.csv",
        index=False,
        encoding="utf-8-sig",
    )

    group_counts = (
        contributor_frame.groupby("group").size().rename("count").reset_index()
        if not contributor_frame.empty
        else pd.DataFrame()
    )
    fetched_at = snapshot.get("fetched_at", "")
    checked_at = (
        pd.Timestamp(fetched_at).tz_convert("Asia/Shanghai").date().isoformat()
        if fetched_at
        else catalog.get("scope", {}).get("checked_at", "")
    )
    report = f"""# BEHAVIOR 网站资源、机器人与贡献者论文型号调研

核验日期：{checked_at}
官网快照：{fetched_at or "未记录"}

## 执行摘要与数量统计

- 网站资源共 {len(resources)} 项。
- 官网贡献者共 {len(contributor_frame)} 人。
- 网站机器人页面实际整理出 {len(robots)} 个条目。
- 已核验贡献者—论文—型号记录共 {len(papers)} 条，覆盖
  {papers["person"].nunique()} 位当前官网贡献者、{papers["paper"].nunique()} 篇论文。
- 待全文核验的贡献者—论文候选共 {len(candidate_frame)} 条。

### 网站机器人类型数量

{markdown_table(site_type_summary)}

### 已核验论文中的型号使用排名

排名主指标为“贡献者—论文—型号”记录数；贡献者数和论文数用于辅助判断。以下均取前 5 名，
当前证据不足 5 个型号时只列已有型号。

#### 纯轮式移动机器人

##### 官网明确提及的型号

BEHAVIOR 官网明确列出了以下 4 种纯轮式移动机器人：

{markdown_table(mobile_site_models)}

其中 LoCoBot 实物平台带有机械臂，但 BEHAVIOR / OmniGibson 文档明确说明其模型中的机械臂被禁用
并固定在底座上，因此本报告按官网运行配置把它归入纯轮式移动机器人。

##### 已核验贡献者论文中的使用排名

{markdown_table(mobile_ranking)}

当前已核验的贡献者论文中，没有发现上述 4 种纯轮式移动机器人作为实验或数据采集平台的明确
型号证据，因此暂时无法给出论文使用频次排名。这里的“无记录”只表示论文核验结果为空，
不表示官网没有提及这些机器人。

#### 机械臂型号

此处统计论文实际使用的机械臂，包括集成在轮式机械臂机器人上的机械臂；它不同于上方网站清单中
“固定机械臂”这一平台类别。

{markdown_table(arm_ranking)}

#### 轮式机械臂机器人

{markdown_table(mobile_manipulator_ranking)}

当前第一名是 Galaxea R1，第二名是 PAL Robotics TIAGo（双臂配置）。该结论只适用于已经完成
型号证据核验的论文集合，不代表机器人学全部论文的市场占有率。

## 采购价格参考

价格快照日期：{price_catalog["snapshot_date"]}。人民币换算采用 {price_catalog["exchange_rates"]["USD"]["rate_date"]}
的统一参考汇率（USD/CNY={price_catalog["exchange_rates"]["USD"]["rate_to_cny"]}，
EUR/CNY={price_catalog["exchange_rates"]["EUR"]["rate_to_cny"]}，
JPY/CNY={price_catalog["exchange_rates"]["JPY"]["rate_to_cny"]}）。人民币金额仅用于横向比较，
不包含来源未明确的税费、运费、关税、安装、软件许可或集成服务。

### 各类别公开数字新品参考范围

{markdown_table(price_category_summary)}

这里的“新品参考”允许同系列当前代或后继配置，但价格表会明确标注匹配关系；历史价、
停产价和低置信第三方估值不进入上述范围。正式价格表不收录二手报价。

### 纯轮式移动机器人价格

{markdown_table(mobile_price_display)}

### 固定机械臂价格

{markdown_table(stationary_arm_price_display)}

### 轮式机械臂机器人价格

{markdown_table(mobile_manipulator_price_display)}

### 非商品虚拟代理

{markdown_table(noncommercial_price_display)}

重要边界：

- 本报告按最新要求不展示任何二手价格；停产型号只保留有日期或可追溯的历史新品价。
- TurtleBot 2 的 USD 1,500 是 IEEE Spectrum 在 2012 年产品原型发布时给出的整机近似价格，
  不是固定报价或当前售价。
- Husky A200 的 EUR 23,353.75 是专业机器人零售商的精确型号新品价；A300 仍仅作后继参考。
- A1 的精确旧型号没有公开价；A1Z 的 USD 2,999 仅作为当前相关型号参考。
- FR3 官网采用询价；Generation Robots 的 EUR 33,180 含税起价是精确商业配置的公开参考。
- Franka Mounted 是项目自定义推车配置，不把 FR3 与推车部件价格自行相加。
- Fetch 与 Freight 属于旧平台，只保留 ROBOTS Guide 的历史新品基础价。
- TIAGo 双臂配置以官网询价为准，USD 30,000–100,000 只是低置信第三方家族区间。
- Stretch 3 的 USD 24,950 是上一代历史新品参考；当前 Stretch 4 官网价为 USD 29,950。
- Galaxea R1 不与 Unitree R1 混用；R1 Lite 2026 的 USD 39,999 仅作旧 R1 后继型号参考。
- BehaviorRobot 是虚拟代理，不是可采购的实体机器人。

## 口径与结论边界

- 官网贡献者：{len(contributor_frame)} 人，覆盖 Core Team、Supporting Team、Alumni。
- 论文窗口：2022-01-01 至 2026-07-01。
- 候选发现：Crossref/OpenAlex 提供论文候选，不直接证明机器人型号。
- 正式明细只接收论文正文、补充材料、官方项目页或官方代码明确支持的型号证据。
- 主排名按“贡献者—论文—型号”记录数；并附不同贡献者数和不同论文数。
- “论文全集”是公开渠道可发现、可核验的集合，不包含未索引或不可访问全文。

## 贡献者覆盖

{markdown_table(group_counts)}

## List 1：网站可提供的资源

{markdown_table(resources)}

{challenge_version_note}

## List 2：网站明确提及或支持的机器人、机械臂

{markdown_table(robot_report_display)}

官网机器人文档正文称支持 12 种机器人，但页面当前实际呈现 14 个条目。本表按页面条目记录，
并保留 Franka Mounted 等配置变体；这类变体不会被悄悄合并成另一型号。

## List 3：贡献者论文中已核验的机器人/机械臂型号

{markdown_table(papers)}

## 型号整体统计

{markdown_table(stats)}

`record_count` 是贡献者—论文—型号记录数；`unique_people` 和 `unique_papers`
分别是去重人数与论文数。榜单只使用 `verification_status=verified` 的明确型号。

## 已确认机器人研究但型号未披露

{markdown_table(unresolved)}

## 自动发现、等待全文核验的候选论文

公共学术索引共保留 {len(candidate_frame)} 条“贡献者—候选论文”记录。为避免把题目或摘要中的
robot 关键词误当作实验平台，这些记录不进入 List 3 和型号排名。完整清单见
[`paper_candidates.csv`](paper_candidates.csv)。

## 可复现方法

1. `python -m scripts.collect_research --discover-crossref` 更新官网名册和无密钥候选；
   有 OpenAlex API key 或匿名服务恢复后可追加 `--discover-openalex`。
2. 对候选论文全文核验实际实验/数据/仿真平台，把证据写入 `data/catalog.json`。
3. `python scripts/build_catalog.py` 重新生成三张主表、未决表、统计表和本报告。
4. `python -m pytest` 验证解析、时间过滤、别名归一化、去重和统计。
"""
    (OUTPUT / "report.md").write_text(report, encoding="utf-8")
    (OUTPUT / "behavior_resource_report.md").write_text(report, encoding="utf-8")
    print(f"contributors={len(contributor_frame)}")
    print(f"resources={len(resources)}")
    print(f"site_robots={len(robots)}")
    print(f"verified_records={len(papers)}")
    print(f"unresolved_records={len(unresolved)}")
    print(f"candidate_records={len(candidate_frame)}")


if __name__ == "__main__":
    main()
