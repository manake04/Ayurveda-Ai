from app.domain.classifier import step


def test_classical_path():
    result = step(["yes"])
    assert result["done"] is True
    assert result["result"]["category"] == "Classical / generic Ayurvedic medicine"


def test_new_drug_path():
    # not classical, not first-schedule-only, not phytopharmaceutical, not food, not cosmetic
    result = step(["no", "no", "no", "no", "no"])
    assert result["done"] is True
    assert result["result"]["category"] == "New / non-classical Ayurvedic drug"


def test_phytopharmaceutical_path():
    result = step(["no", "no", "yes"])
    assert result["done"] is True
    assert result["result"]["category"] == "Phytopharmaceutical drug"


def test_ayurveda_aahar_path():
    result = step(["no", "no", "no", "yes"])
    assert result["done"] is True
    assert result["result"]["category"] == "Ayurveda-Aahar / nutraceutical"


def test_proprietary_e1_path():
    result = step(["no", "yes", "yes"])
    assert result["done"] is True
    assert result["result"]["category"] == "Patent-or-proprietary Ayurvedic medicine (Schedule E(1) route)"


def test_incomplete_path_returns_next_question():
    result = step(["no"])
    assert result["done"] is False
    assert result["question_id"] == "q2_only_first_schedule_ingredients"
    assert result["options"] == ["yes", "no"]


def test_invalid_answer_raises():
    import pytest

    with pytest.raises(ValueError):
        step(["maybe"])


def test_every_leaf_has_relevant_corpus_ids():
    from app.domain.classifier import TREE

    for node_id, node in TREE.items():
        if node["type"] == "result":
            assert node["relevant_corpus_ids"], f"{node_id} has no corpus citations"
