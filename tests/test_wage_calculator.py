"""Unit tests for wage and statutory calculations."""

from modules.statutory_calculator import calculate_esic, calculate_pf, calculate_pt
from modules.wage_calculator import calculate_wages


def test_labour_wage_calculation():
    result = calculate_wages(
        {
            "emp_code": "E001",
            "emp_name": "Test Labour",
            "designation": "Labour",
            "present_days": 26,
            "ot_hours": 0,
        },
        month=1,
    )
    assert result["basic_wages"] == 20425.08


def test_ot_calculation():
    result = calculate_wages(
        {"emp_code": "E001", "emp_name": "Test Labour", "designation": "Labour", "present_days": 0, "ot_hours": 112},
        month=1,
    )
    assert result["ot_amount"] == 10318.56


def test_pf_calculation():
    employee_pf, employer_pf = calculate_pf(20425.08)
    assert employee_pf == 2451.01
    assert employer_pf == 2655.26


def test_esic_calculation():
    emp, employer, applicable = calculate_esic(15000)
    assert (emp, employer, applicable) == (112.5, 487.5, True)
    emp2, employer2, applicable2 = calculate_esic(25000)
    assert (emp2, employer2, applicable2) == (0.0, 0.0, False)


def test_pt_calculation():
    assert calculate_pt(9000, 1) == 0
    assert calculate_pt(15000, 1) == 175
    assert calculate_pt(30000, 1) == 300
    assert calculate_pt(15000, 2) == 475

