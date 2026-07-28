from __future__ import annotations

import logging
from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from backend.services.profile_service import get_profile

log = logging.getLogger(__name__)

_driver: WebDriver | None = None

FIELD_SELECTORS = {
    "name": ["input[name='name']", "input[id*='name']", "input[placeholder*='Name']"],
    "email": ["input[type='email']", "input[name='email']", "input[id*='email']"],
    "phone": ["input[type='tel']", "input[name='phone']", "input[id*='phone']", "input[name='mobile']"],
    "college": ["input[name='college']", "input[id*='college']", "input[placeholder*='College']", "input[name='institution']"],
    "usn": ["input[name='usn']", "input[id*='usn']", "input[placeholder*='USN']"],
    "branch": ["input[name='branch']", "input[id*='branch']", "select[name='branch']", "select[id*='branch']"],
    "degree": ["input[name='degree']", "input[id*='degree']", "select[name='degree']", "select[id*='degree']"],
    "cgpa": ["input[name='cgpa']", "input[id*='cgpa']", "input[name='gpa']", "input[placeholder*='CGPA']", "input[placeholder*='GPA']"],
    "skills": ["textarea[name='skills']", "input[name='skills']", "textarea[id*='skills']", "input[placeholder*='Skills']"],
}

PROFILE_FIELD_MAP: dict[str, str | None] = {
    "name": "name",
    "email": "email",
    "phone": "phone",
    "college": None,
    "usn": None,
    "branch": "branch",
    "degree": "degree",
    "cgpa": "percentage",
    "skills": None,
}


def _get_driver() -> WebDriver:
    global _driver
    if _driver is None:
        options = Options()
        options.add_argument("--start-maximized")
        _driver = webdriver.Chrome(options=options)
    return _driver


def _detect_form_fields(driver: WebDriver) -> dict[str, dict[str, Any]]:
    fields: dict[str, dict[str, Any]] = {}
    for field_name, selectors in FIELD_SELECTORS.items():
        for selector in selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                el = elements[0]
                tag = el.tag_name
                fields[field_name] = {
                    "tag": tag,
                    "selector": selector,
                    "current_value": el.get_attribute("value") or "",
                }
                break
    return fields


def start_autofill(url: str, profile_id: str) -> dict[str, Any]:
    profile = get_profile(profile_id)
    if not profile:
        return {"error": "Profile not found"}

    driver = _get_driver()
    driver.get(url)

    fields = _detect_form_fields(driver)
    filled: list[str] = []
    missing: list[str] = []

    for field_name, field_info in fields.items():
        profile_key = PROFILE_FIELD_MAP.get(field_name)
        value = profile.get(profile_key) if profile_key else None
        if value is None:
            missing.append(field_name)
            continue

        try:
            el = driver.find_element(By.CSS_SELECTOR, field_info["selector"])
            el.clear()
            el.send_keys(str(value))
            filled.append(field_name)
        except Exception:
            missing.append(field_name)

    return {
        "status": "started",
        "url": driver.current_url,
        "filled": filled,
        "missing": missing,
    }


def get_form_state() -> dict[str, Any]:
    driver = _get_driver()
    fields = _detect_form_fields(driver)
    filled: list[str] = []
    missing: list[str] = []

    for field_name, field_info in fields.items():
        if field_info["current_value"]:
            filled.append(field_name)
        else:
            missing.append(field_name)

    return {
        "url": driver.current_url,
        "filled": filled,
        "missing": missing,
    }


def close_browser() -> dict[str, Any]:
    global _driver
    if _driver is not None:
        try:
            _driver.quit()
        except Exception:
            pass
        _driver = None
    return {"status": "closed"}
