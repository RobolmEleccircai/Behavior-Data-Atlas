import pandas as pd

from behavior_reader.research import (
    extract_challenge_page_title,
    extract_site_metadata,
    expand_paper_records,
    model_statistics,
    normalize_model,
    normalize_name,
    parse_contributors,
)
from scripts.build_catalog import usage_ranking


def test_parse_contributors_preserves_groups_and_homepages() -> None:
    html = """
    <h4>Core Team</h4><div><a href="https://a.example">Áda Robot</a></div>
    <h4>Supporting Team</h4><p><a href="https://b.example">Bob Arm</a></p>
    <h4>Alumni</h4><p><a href="https://c.example">Chen Base</a></p>
    <h4>Contact</h4><p><a href="mailto:test@example.com">not a member</a></p>
    """
    rows = parse_contributors(html, "https://behavior.stanford.edu/")

    assert [row["group"] for row in rows] == [
        "Core Team",
        "Supporting Team",
        "Alumni",
    ]
    assert rows[0]["homepage"] == "https://a.example"


def test_parse_current_team_card_markup_and_unlinked_alumni() -> None:
    html = """
    <div class="team-category">
      <h4 class="team-title">Core Team</h4>
      <div class="team-member">
        <a href="https://ada"><img alt="Ada"></a>
        <small class="team-name">Ada Robot</small>
      </div>
    </div>
    <div class="team-category">
      <h4 class="team-title">Alumni</h4>
      <div><span class="alumni-name">No Homepage</span></div>
    </div>
    """
    rows = parse_contributors(html, "https://behavior.stanford.edu/")

    assert rows == [
        {
            "name": "Ada Robot",
            "group": "Core Team",
            "homepage": "https://ada",
            "source_url": "https://behavior.stanford.edu/",
        },
        {
            "name": "No Homepage",
            "group": "Alumni",
            "homepage": "",
            "source_url": "https://behavior.stanford.edu/",
        },
    ]


def test_model_and_name_aliases_are_normalized() -> None:
    assert normalize_model("Panda") == "Franka Emika Panda"
    assert normalize_model("TIAGo") == "PAL Robotics TIAGo (dual-arm configuration)"
    assert normalize_name("Roberto Martín-Martín") == "roberto martin martin"
    assert normalize_name("Chengshu (Eric) Li") == normalize_name("Chengshu Li")
    assert normalize_name("Chengshu Li") != normalize_name("Chengshu Liwei")


def test_extracts_current_challenge_name() -> None:
    html = '<a href="/challenge/">🏆 2026 BEHAVIOR Challenge</a>'
    assert extract_site_metadata(html) == {
        "challenge_name": "2026 BEHAVIOR Challenge"
    }
    assert (
        extract_challenge_page_title(
            "<title>2025 BEHAVIOR Challenge - BEHAVIOR</title>"
        )
        == "2025 BEHAVIOR Challenge"
    )


def test_expand_filters_years_roster_and_deduplicates() -> None:
    contributors = [
        {"name": "Ada", "group": "Core Team", "homepage": "https://ada", "source_url": ""}
    ]
    model = {
        "model": "Panda",
        "entity_type": "robot",
        "robot_type": "stationary manipulator",
        "arm_model": "Panda",
        "end_effector": "Franka Hand",
        "evidence": "Methods section names the robot.",
        "verification_status": "verified",
    }
    papers = [
        {
            "title": "Current",
            "year": 2024,
            "paper_url": "https://paper",
            "authors": [{"name": "Ada"}, {"name": "Someone Else"}],
            "models": [model, model],
        },
        {
            "title": "Too old",
            "year": 2021,
            "paper_url": "https://old",
            "authors": [{"name": "Ada"}],
            "models": [model],
        },
    ]

    records, unresolved = expand_paper_records(papers, contributors)

    assert len(records) == 1
    assert records.iloc[0]["model_canonical"] == "Franka Emika Panda"
    assert unresolved.empty


def test_statistics_use_records_as_primary_count_and_split_entities() -> None:
    rows = pd.DataFrame(
        [
            {
                "person": "Ada",
                "paper": "P1",
                "model_canonical": "Galaxea R1",
                "arm_model": "R1 arm",
                "end_effector": "parallel gripper",
                "verification_status": "verified",
            },
            {
                "person": "Bob",
                "paper": "P1",
                "model_canonical": "Galaxea R1",
                "arm_model": "R1 arm",
                "end_effector": "parallel gripper",
                "verification_status": "verified",
            },
            {
                "person": "Ada",
                "paper": "P2",
                "model_canonical": "Galaxea R1",
                "arm_model": "R1 arm",
                "end_effector": "parallel gripper",
                "verification_status": "partial",
            },
        ]
    )

    stats = model_statistics(rows)
    robot = stats[(stats["entity_type"] == "robot")].iloc[0]

    assert robot["record_count"] == 2
    assert robot["unique_people"] == 2
    assert set(stats["entity_type"]) == {"robot", "arm", "end_effector"}


def test_usage_ranking_filters_robot_category() -> None:
    rows = pd.DataFrame(
        [
            {
                "person": "Ada",
                "paper": "P1",
                "model_canonical": "Mobile Arm",
                "robot_type": "mobile manipulator",
                "verification_status": "verified",
            },
            {
                "person": "Bob",
                "paper": "P1",
                "model_canonical": "Mobile Arm",
                "robot_type": "mobile manipulator",
                "verification_status": "verified",
            },
            {
                "person": "Ada",
                "paper": "P2",
                "model_canonical": "Mobile Base",
                "robot_type": "mobile robot",
                "verification_status": "verified",
            },
        ]
    )

    ranking = usage_ranking(rows, {"mobile manipulator"})

    assert ranking.iloc[0].to_dict() == {
        "排名": 1,
        "型号": "Mobile Arm",
        "记录数": 2,
        "贡献者数": 2,
        "论文数": 1,
    }
