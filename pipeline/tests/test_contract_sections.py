from statsboteval_pipeline.contract import (
    LanguageSection,
    LanguageTotals,
    LanguageWeekly,
    LanguageWindow,
    MessagesByLanguage,
    Sections,
    UsageContextTotals,
    UsageContextWindow,
    UserClasses,
    WeeklyEntry,
    WeeklySeries,
    dump_doc,
    ok,
)


def one_series() -> WeeklySeries:
    return WeeklySeries(series=[WeeklyEntry(week="2025-W11", cell=ok(3))])


def test_sections_all_optional() -> None:
    assert dump_doc(Sections()) == {}


def test_language_section_shape() -> None:
    lang = LanguageSection(
        weekly=LanguageWeekly(
            messages_by_language=MessagesByLanguage(
                de=one_series(), en=one_series(), other=one_series(), undetermined=one_series(),
                footnote_ids=["language_heuristic"],
            )
        ),
        per_window={"all_time": LanguageWindow(totals=LanguageTotals(de=ok(9), en=ok(4), other=ok(0), undetermined=ok(0)))},
    )
    dumped = dump_doc(lang)
    assert set(dumped["weekly"]["messages_by_language"].keys()) == {"de", "en", "other", "undetermined", "footnote_ids"}
    assert dumped["per_window"]["all_time"]["totals"]["other"] == {"status": "ok", "value": 0}


def test_usage_context_1_3_0_shape_still_validates() -> None:
    """Additive proof for 1.4.0 (D-50): the 1.3.0 usage_context stays legal.

    A window written before the Adoption additions carries neither the retention pair,
    the signup-activation count, `frequent`, nor `by_status` — and must round-trip
    without gaining null keys, so a 1.3.0 reader sees exactly what it always saw.
    """
    old = UsageContextWindow(
        totals=UsageContextTotals(
            active_students=ok(58), messages=ok(412), sessions=ok(163), new_registrations=ok(21)
        ),
        user_classes=UserClasses(one_time=ok(31), monthly=ok(6), sporadic=ok(21)),
    )
    dumped = dump_doc(old)
    assert set(dumped["totals"]) == {"active_students", "messages", "sessions", "new_registrations"}
    assert set(dumped["user_classes"]) == {"one_time", "monthly", "sporadic"}
    assert "by_status" not in dumped
    assert UsageContextWindow.model_validate(dumped) == old
