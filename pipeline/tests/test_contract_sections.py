from statsboteval_pipeline.contract import (
    LanguageSection,
    LanguageTotals,
    LanguageWeekly,
    LanguageWindow,
    MessagesByLanguage,
    Sections,
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
